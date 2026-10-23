"""SDK spans follow the GenAI conventions without content; the harness detects a silent
model swap and stays quiet on noise; calibration and the suite gate behave."""
import pathlib
import subprocess
import sys
import time
import urllib.request

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "observability"))
import platform_eval as harness  # noqa: E402

EXPORTER = InMemorySpanExporter()
_provider = TracerProvider()
_provider.add_span_processor(SimpleSpanProcessor(EXPORTER))
trace.set_tracer_provider(_provider)
import platform_sdk  # noqa: E402


@pytest.fixture(scope="module")
def gateway_url():
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    env = {"PYTHONPATH": str(ROOT / "gateway"), "PLATFORM_METERING_SINK": "memory", "PATH": "/usr/bin:/bin"}
    p = subprocess.Popen([sys.executable, "-m", "platform_gateway.server", "--mock", "--env", "local",
                          "--port", str(port)], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    url = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            urllib.request.urlopen(url + "/healthz", timeout=1)
            break
        except OSError:
            time.sleep(0.1)
    yield url
    p.terminate()


def test_sdk_span_attributes_and_no_content(gateway_url):
    gw = platform_sdk.Gateway(gateway_url, "lab-key-tenant-a",
                              platform_sdk.Context("tenant-a", "warranty-answer", "c-9"),
                              prices={"model-a": {"input": 3.0, "output": 15.0}})
    r = gw.chat([{"role": "user", "content": "secret customer question"}])
    assert r.status == 200
    span = [s for s in EXPORTER.get_finished_spans() if s.name == "chat standard"][-1]
    a = dict(span.attributes)
    assert a["gen_ai.operation.name"] == "chat" and a["gen_ai.request.model"] == "standard"
    assert a["gen_ai.response.model"] == "mock/model-a"
    assert a["platform.tenant"] == "tenant-a" and a["platform.feature"] == "warranty-answer"
    assert a["gen_ai.usage.input_tokens"] > 0 and a["platform.cost_usd"] > 0
    assert not any("secret customer question" in str(v) for v in a.values())
    # trace context propagated: the gateway saw the SDK's trace ID
    assert r.trace_id == format(span.context.trace_id, "032x")


def test_detector_alarms_on_silent_swap_and_not_on_noise():
    j = harness.MockJudge()
    base = [j.score("q", f"[model-a:strong] answer {i}") for i in range(60)]
    det = harness.RegressionDetector(base)
    assert all(det.observe(j.score("q", f"[model-a:strong] more {i}"), f"t{i}") is None for i in range(40))
    alarm = None
    for i in range(30):
        alarm = alarm or det.observe(j.score("q", f"[model-weak:weak] answer {i}"), f"weak-{i}")
    assert alarm and alarm.window_mean < alarm.baseline_mean
    assert all(t.startswith("weak-") for t in alarm.trace_ids)


def test_sampling_is_deterministic_and_close_to_rate():
    ids = [f"{i:032x}" for i in range(20000)]
    rate = sum(harness.sampled(t, 0.05) for t in ids) / len(ids)
    assert 0.04 < rate < 0.06
    assert harness.sampled(ids[7], 0.05) == harness.sampled(ids[7], 0.05)


def test_calibration_kappa():
    human = [True] * 14 + [False] * 6
    good = harness.calibration(human[:], human)
    assert good["kappa"] == 1.0 and good["trust"] == "ok"
    lenient = harness.calibration([True] * 20, human)
    assert lenient["kappa"] == 0.0 and lenient["trust"] == "recalibrate"


def test_suite_gate(tmp_path):
    suite = ROOT / "blueprints" / "rag-service" / "skeleton" / "evals" / "warranty" / "suite.yaml"
    if not suite.exists():
        pytest.skip("blueprint not present")
    good = lambda q: (("[model-p:strongest] Covered with conditions." if "water" in q else "I can't advise on legal action."),
                      ["policy/extended-plan.md#water"] if "water" in q else [])
    bad = lambda q: ("[model-weak:weak] Yes.", [])
    assert harness.run_suite(str(suite), good, harness.MockJudge())["gate"] == "pass"
    assert harness.run_suite(str(suite), bad, harness.MockJudge())["gate"] == "fail"
