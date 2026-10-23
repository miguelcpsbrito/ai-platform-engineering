"""labs/ch08 — see one interaction all the way down (Section 8.7), local mode.

1. One interaction as a trace: the SDK span with GenAI attributes and cost, joined to
   the gateway's metering event by trace ID.
2. Level-3 setup: a twenty-case golden set labelled by a 'human' (scripted here) and the
   judge's calibration against it.
3. The planted incident: the alias behind the service flips to a weaker model — no
   deploy, no error-rate change — and the detection chain fires. Elapsed time is reported
   in simulated minutes at the lab's traffic rate (default 60 requests/minute).
"""
import argparse
import json
import os
import pathlib
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

LAB = pathlib.Path(__file__).resolve().parent
ROOT = LAB.parents[1]
sys.path.insert(0, str(ROOT / "observability"))
EXP = InMemorySpanExporter()
_p = TracerProvider()
_p.add_span_processor(SimpleSpanProcessor(EXP))
trace.set_tracer_provider(_p)
import platform_eval as harness  # noqa: E402
import platform_sdk  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rpm", type=int, default=60, help="simulated traffic, requests per minute")
    ap.add_argument("--sample-rate", type=float, default=0.05)
    a = ap.parse_args()
    work = pathlib.Path(tempfile.mkdtemp(prefix="ch08-"))
    cfg = work / "gw"
    shutil.copytree(ROOT / "gateway", cfg, ignore=shutil.ignore_patterns("tests", "terraform", "build", "__pycache__"))
    metering = work / "metering.jsonl"
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    env = dict(os.environ, PYTHONPATH=str(ROOT / "gateway"), PLATFORM_METERING_SINK="file",
               PLATFORM_METERING_FILE=str(metering))
    proc = subprocess.Popen([sys.executable, "-m", "platform_gateway.server", "--mock", "--env", "local",
                             "--port", str(port), "--config", str(cfg)], env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    url = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            urllib.request.urlopen(url + "/healthz", timeout=1)
            break
        except OSError:
            time.sleep(0.1)
    try:
        gw = platform_sdk.Gateway(url, "lab-key-tenant-b", platform_sdk.Context("tenant-b", "warranty-answer"),
                                  prices={"model-a": {"input": 3.0, "output": 15.0}})
        r = gw.chat([{"role": "user", "content": "Is water damage covered on the extended plan?"}])
        span = EXP.get_finished_spans()[-1]
        ev = [json.loads(l) for l in metering.read_text().splitlines() if r.trace_id in l][0]
        print("1  one interaction, all the way down")
        print("   span  ", json.dumps({k: v for k, v in span.attributes.items()}))
        print("   meter ", json.dumps({k: ev[k] for k in ("trace_id", "tenant", "feature", "model", "region",
                                                         "tokens_in", "tokens_out", "cost_usd")}))

        judge = harness.MockJudge()
        golden = [(f"[model-a:strong] case {i}", True) for i in range(14)] + \
                 [(f"[model-weak:weak] case {i}", False) for i in range(6)]
        cal = harness.calibration([judge.score("q", t) >= 0.7 for t, _ in golden], [h for _, h in golden])
        print(f"2  judge calibration on a 20-case golden set: {cal}")

        base = [judge.score("q", gw.chat([{"role": "user", "content": f"baseline {i}"}]).text) for i in range(40)]
        det = harness.RegressionDetector(base)
        overlay = cfg / "env" / "local.yaml"
        overlay.write_text(overlay.read_text().replace("local:   { model: mock/model-a }",
                                                       "local:   { model: mock/model-weak }"))
        req = urllib.request.Request(url + "/admin/reload", data=json.dumps({"base": str(cfg)}).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
        urllib.request.urlopen(req, timeout=10)
        n, first_sample, alarm = 0, None, None
        while not alarm and n < 20000:
            r = gw.chat([{"role": "user", "content": f"production question {n}"}])
            n += 1
            if r.status == 200 and harness.sampled(r.trace_id, a.sample_rate):
                first_sample = first_sample or n
                alarm = det.observe(judge.score("q", r.text), r.trace_id)
        errors = [s for s in EXP.get_finished_spans() if s.status.status_code.name == "ERROR"]
        mins = lambda k: k / a.rpm
        print(f"3  alias flipped to a weaker model at minute 0 (no deploy; spans with errors: {len(errors)})")
        print(f"   first sampled judgment on the new model: minute {mins(first_sample):.0f}")
        print(f"   regression alarm: minute {mins(n):.0f} — {alarm.text() if alarm else 'NO ALARM'}")
        print(f"   (target from Table 8.8: under an hour at {a.sample_rate:.0%} sampling)")
        sys.exit(0 if alarm and mins(n) < 60 else 1)
    finally:
        proc.terminate()


if __name__ == "__main__":
    main()
