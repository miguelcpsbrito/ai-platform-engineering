"""labs/ch04 — the four proofs of Table 4.9, local mode (no AWS account, no cost).

Starts the reference gateway with simulated models, then runs each proof as a scripted
scenario and prints the artifact it produced. Exit code 0 means all four passed.

    python labs/ch04/prove_local.py            # all proofs
    python labs/ch04/prove_local.py --only 2   # one proof

The AWS track (README.md) runs the same proofs against the proxy on EKS.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import hashlib
import json
import pathlib
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

LAB = pathlib.Path(__file__).resolve().parent
ROOT = LAB.parents[1]
sys.path.insert(0, str(ROOT / "gateway"))
sys.path.insert(0, str(LAB))

import app  # noqa: E402  (the application under test)

KEY_A, KEY_B = "lab-key-tenant-a", "lab-key-tenant-b"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_ready(url, timeout=20):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            urllib.request.urlopen(url + "/healthz", timeout=1)
            return
        except OSError:
            time.sleep(0.2)
    raise SystemExit("gateway did not start")


def admin(url, path, body=None):
    req = urllib.request.Request(url + path, data=json.dumps(body or {}).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def events(path: pathlib.Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def p95(xs):
    xs = sorted(xs)
    return xs[max(0, int(round(0.95 * len(xs))) - 1)]


# --- proof 1 -------------------------------------------------------------------------------
def proof_swap(url, cfg_dir: pathlib.Path):
    """Change `standard` from model A to model B in config; the application diff is empty."""
    app_hash = hashlib.sha256((LAB / "app.py").read_bytes()).hexdigest()
    before = app.ask("What does the extended plan cover?", url=url)[1].get("x-platform-served-by")
    overlay = cfg_dir / "env" / "local.yaml"
    overlay.write_text(overlay.read_text().replace("local:   { model: mock/model-a }",
                                                   "local:   { model: mock/model-b }"))
    admin(url, "/admin/reload", {"base": str(cfg_dir)})
    after = app.ask("What does the extended plan cover?", url=url)[1].get("x-platform-served-by")
    same_code = hashlib.sha256((LAB / "app.py").read_bytes()).hexdigest() == app_hash
    ok = before == "mock/model-a" and after == "mock/model-b" and same_code
    return ok, {"served_before": before, "served_after": after,
                "application_diff": "empty" if same_code else "CHANGED"}


# --- proof 2 -------------------------------------------------------------------------------
def flood(url, i):
    """One request of tenant A's synthetic load (module-level so worker processes can run it)."""
    s, h, body = app.ask("summarize this long policy " + "lorem " * 800, key=KEY_A, url=url,
                         feature="bulk-summary", max_tokens=2048)
    return s, (body.get("error"), body.get("limit"), h.get("Retry-After") is not None)


def proof_quota(url, n_probe=40):
    """10x synthetic load on tenant A; A gets 429s with a cause, B's p95 moves < 10%."""
    def b_latency():
        t0 = time.perf_counter()
        s, _, _ = app.ask("status of order 1182?", key=KEY_B, url=url, feature="order-status")
        return (time.perf_counter() - t0) * 1000, s

    base = [b_latency()[0] for _ in range(n_probe)]
    # The flood runs in other processes, so the probe measures the gateway, not the client.
    with cf.ProcessPoolExecutor(max_workers=5) as ex:
        futs = [ex.submit(flood, url, i) for i in range(10 * n_probe)]
        time.sleep(0.5)
        loaded = [b_latency() for _ in range(n_probe)]
        results = [f.result() for f in futs]
    a_status = [r[0] for r in results]
    causes = {r[1] for r in results if r[0] == 429}
    loaded_ms = [x for x, s in loaded if s == 200]
    b_ok = len(loaded_ms) == n_probe
    base_p95, loaded_p95 = p95(base), p95(loaded_ms) if loaded_ms else float("inf")
    # 10% relative, with a 5 ms floor for timer noise on a laptop
    within = loaded_p95 <= base_p95 * 1.10 + 5
    n429 = a_status.count(429)
    ok = n429 > 0 and b_ok and within and ("tenant_quota_exceeded", "tokens_per_minute", True) in causes
    return ok, {"tenant_a_requests": len(a_status), "tenant_a_429": n429, "429_causes": sorted(causes),
                "tenant_b_p95_ms_baseline": round(base_p95, 1), "tenant_b_p95_ms_under_load": round(loaded_p95, 1),
                "tenant_b_all_succeeded": b_ok}


# --- proof 3 -------------------------------------------------------------------------------
def proof_fallback(url, metering: pathlib.Path, n=30, threshold=0.05):
    """Fail the primary region; requests succeed and the fallback-rate alert fires."""
    admin(url, "/admin/faults", {"rules": [{"match": "model-b@us-east-1", "error_rate": 1.0},
                                           {"match": "model-a@us-east-1", "error_rate": 1.0}]})
    start = len(events(metering))
    statuses = [app.ask(f"warranty question {i}", key=KEY_B, url=url, feature="warranty-answer")[0]
                for i in range(n)]
    admin(url, "/admin/faults/clear")
    window = [e for e in events(metering)[start:] if e["status"] == 200]
    rate = sum(1 for e in window if e["fallback"]) / max(len(window), 1)
    alert = rate > threshold
    ok = all(s == 200 for s in statuses) and alert
    return ok, {"requests": n, "succeeded": statuses.count(200), "fallback_rate": round(rate, 3),
                "alert": f"ALERT fallback_rate {rate:.0%} > {threshold:.0%} (alias standard, us-east-1)"
                if alert else "no alert", "served_from": sorted({e["region"] for e in window})}


# --- proof 4 -------------------------------------------------------------------------------
def proof_cost(metering: pathlib.Path):
    """Spend per tenant per feature from gateway events alone, with the packaged query."""
    import duckdb
    day = dt.datetime.now(dt.timezone.utc).date().isoformat()   # local data is today's
    con = duckdb.connect()
    con.execute(f"""CREATE VIEW gateway_events AS
                    SELECT *, strftime(CAST(ts AS TIMESTAMPTZ) AT TIME ZONE 'UTC', '%Y-%m-%d') AS dt
                    FROM read_json_auto('{metering}')""")
    sql = (LAB / "cost_by_feature.sql").read_text().replace("{{day}}", day)
    t0 = time.perf_counter()
    rows = con.execute(sql).fetchall()
    cols = [d[0] for d in con.description]
    ms = (time.perf_counter() - t0) * 1000
    table = [dict(zip(cols, r)) for r in rows]
    ok = len(table) >= 3 and all(r["cost_usd"] > 0 for r in table)
    return ok, {"query": "labs/ch04/cost_by_feature.sql", "ms": round(ms, 1), "rows": table}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", type=int)
    ap.add_argument("--port", type=int, default=0)
    a = ap.parse_args()
    work = pathlib.Path(tempfile.mkdtemp(prefix="ch04-"))
    cfg_dir = work / "gateway-config"
    shutil.copytree(ROOT / "gateway", cfg_dir, ignore=shutil.ignore_patterns("tests", "terraform", "build", "__pycache__"))
    metering = work / "metering.jsonl"
    port = a.port or free_port()
    # The gateway runs in its own process, as it would in production: the load generator
    # must not share an interpreter (or a GIL) with the system under test.
    env = dict(os.environ, PLATFORM_METERING_SINK="file", PLATFORM_METERING_FILE=str(metering),
               PYTHONPATH=str(ROOT / "gateway"))
    proc = subprocess.Popen([sys.executable, "-m", "platform_gateway.server", "--mock", "--env", "local",
                             "--port", str(port), "--config", str(cfg_dir)], env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    url = f"http://127.0.0.1:{port}"
    wait_ready(url)
    proofs = [(1, "Swap without code", lambda: proof_swap(url, cfg_dir)),
              (2, "Quota isolation", lambda: proof_quota(url)),
              (3, "Fallback", lambda: proof_fallback(url, metering)),
              (4, "Cost per feature", lambda: proof_cost(metering))]
    failed = 0
    for n, name, fn in proofs:
        if a.only and a.only != n:
            continue
        ok, artifact = fn()
        failed += not ok
        print(f"{'PASS' if ok else 'FAIL'}  proof {n} — {name}")
        print("      " + json.dumps(artifact, default=str, indent=2).replace("\n", "\n      "))
    proc.terminate()
    print(f"\nmetering events: {metering}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
