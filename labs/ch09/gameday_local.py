"""labs/ch09 — the scripted game day (Section 9.7), local mode.

Phase 1 (I-1 + I-2): the fault layer slows the primary region's `standard` model and
silently swaps in a weaker one. The level-3 detector must tell 'slower' from 'worse';
the responder executes RB-2 step 4 (pin the alias to the fallback model).
Phase 2 (I-5): the shared pool saturates (throttling on the pinned model); the
degradation ladder moves opted-in tenants to `fast`, others queue or shed.
Scores: detection→classification, classification→mitigation, and comms latency. The
postmortem skeleton (docs/templates/postmortem.md) is filled from the run's timeline.

    python labs/ch09/gameday_local.py               # scripted responder
    python labs/ch09/gameday_local.py --interactive # you make each decision
"""
import argparse
import datetime as dt
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

LAB = pathlib.Path(__file__).resolve().parent
ROOT = LAB.parents[1]
sys.path.insert(0, str(ROOT / "observability"))
sys.path.insert(0, str(ROOT / "labs" / "ch04"))
import app  # noqa: E402
import platform_eval as harness  # noqa: E402

TIMELINE = []


def mark(event, **kw):
    TIMELINE.append({"t": time.perf_counter(), "event": event, **kw})
    print(f"[{len(TIMELINE):02d}] {event} {json.dumps(kw) if kw else ''}")


def admin(url, path, body=None):
    req = urllib.request.Request(url + path, data=json.dumps(body or {}).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    return json.loads(urllib.request.urlopen(req, timeout=10).read())


def start(cfg_dir):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    env = dict(os.environ, PYTHONPATH=str(ROOT / "gateway"), PLATFORM_METERING_SINK="memory")
    p = subprocess.Popen([sys.executable, "-m", "platform_gateway.server", "--mock", "--env", "local",
                          "--port", str(port), "--config", str(cfg_dir)], env=env,
                         stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    url = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            urllib.request.urlopen(url + "/healthz", timeout=1)
            return p, url
        except OSError:
            time.sleep(0.1)


def decide(prompt, default, interactive):
    if not interactive:
        return default
    ans = input(f"\n{prompt} [{default}] > ").strip()
    return ans or default


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--interactive", action="store_true")
    ap.add_argument("--sample-rate", type=float, default=0.3)
    a = ap.parse_args()
    work = pathlib.Path(tempfile.mkdtemp(prefix="ch09-"))
    cfg = work / "gw"
    shutil.copytree(ROOT / "gateway", cfg, ignore=shutil.ignore_patterns("tests", "terraform", "build", "__pycache__"))
    proc, url = start(cfg)
    judge = harness.MockJudge()
    base = [judge.score("q", app.ask(f"baseline {i}", key="lab-key-tenant-b", url=url)[2]["choices"][0]["message"]["content"])
            for i in range(30)]
    det = harness.RegressionDetector(base)
    comms = []
    try:
        mark("game day start", scenario="I-1 latency + I-2 silent swap on standard@us-east-1")
        admin(url, "/admin/faults", {"rules": [{"match": "model-a@us-east-1", "latency_ms": 120, "swap_to": "model-weak"}]})
        mark("fault injected")
        alarm, i = None, 0
        while not alarm and i < 400:
            s, h, body = app.ask(f"warranty question {i}", key="lab-key-tenant-b", url=url, feature="warranty-answer")
            tid = h.get("x-platform-trace-id")
            if s == 200 and harness.sampled(tid, a.sample_rate):
                alarm = det.observe(judge.score("q", body["choices"][0]["message"]["content"]), tid)
            i += 1
        mark("detector fired", alarm=alarm.text() if alarm else None, requests=i)
        kind = decide("Classify: slower (I-1) or worse (I-2)?", "I-2", a.interactive)
        mark("classified", type=kind, evidence="score drop on sampled answers; error rate unchanged")
        comms.append(("investigating", time.perf_counter()))
        mark("comms: investigating", channel="#tenant-cx", text="standard answers degraded since game-day start; investigating")
        action = decide("RB-2 step 4: pin standard to the fallback model? (pin/rollback)", "pin", a.interactive)
        overlay = cfg / "env" / "local.yaml"
        overlay.write_text(overlay.read_text().replace("local:   { model: mock/model-a }", "local:   { model: mock/model-c }"))
        admin(url, "/admin/reload", {"base": str(cfg)})
        mark("mitigated", action=f"RB-2 {action}: standard → mock/model-c (fallback model, contract allows)")
        comms.append(("mitigated", time.perf_counter()))
        mark("comms: mitigated", channel="#tenant-cx", text="standard pinned to fallback model; answers may differ in style")
        rec = [judge.score("q", app.ask(f"verify {k}", key="lab-key-tenant-b", url=url)[2]["choices"][0]["message"]["content"])
               for k in range(15)]
        mark("verified", mean_score=round(sum(rec) / len(rec), 3), baseline=round(det.mu, 3))

        mark("phase 2", scenario="I-5 shared pool saturates (throttling on the pinned model)")
        admin(url, "/admin/faults", {"rules": [{"match": "model-c@*", "error_rate": 0.7}]})
        results = {"tenant-a": {}, "tenant-b": {}}
        for k in range(60):
            for t, key in (("tenant-a", "lab-key-tenant-a"), ("tenant-b", "lab-key-tenant-b")):
                s, h, _ = app.ask(f"pool {k}", key=key, url=url)
                tag = h.get("x-platform-degraded", "served") if s == 200 else str(s)
                results[t][tag] = results[t].get(tag, 0) + 1
        mark("ladder", tenant_a=results["tenant-a"], tenant_b=results["tenant-b"],
             note="tenant-a opted into cheaper_alias; tenant-b's ladder is queue → shed")
        admin(url, "/admin/faults/clear")
        mark("game day end")
    finally:
        proc.terminate()

    t = {e["event"]: e["t"] for e in TIMELINE}
    scores = {
        "detection_s": round(t["detector fired"] - t["fault injected"], 2),
        "detection_to_classification_s": round(t["classified"] - t["detector fired"], 2),
        "classification_to_mitigation_s": round(t["mitigated"] - t["classified"], 2),
        "comms_latency_s": round(comms[0][1] - t["detector fired"], 2),
    }
    print("\nSCORES", json.dumps(scores))
    pm = (ROOT / "docs" / "templates" / "postmortem.md").read_text()
    stamp = dt.date.today().isoformat()
    filled = pm.replace("<date>", stamp).replace("<slug>", "gameday-standard-swap")
    filled += "\n\n## Timeline (from this run)\n" + "\n".join(
        f"- +{e['t'] - TIMELINE[0]['t']:.2f}s {e['event']}" for e in TIMELINE)
    filled += f"\n\n## Detection audit\n- Detector: level-3 regression detector (sampling {a.sample_rate:.0%}); " \
              f"fired after {scores['detection_s']}s.\n- Would have caught it sooner: higher sampling on critical tenants.\n"
    out = work / f"PM-{stamp}-gameday.md"
    out.write_text(filled)
    print(f"postmortem draft: {out}")
    ok = TIMELINE and alarm and results["tenant-a"].get("cheaper_alias", 0) > 0
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
