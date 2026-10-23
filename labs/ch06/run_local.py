"""labs/ch06 — steps 5–8 of Table 6.7 in local mode (DuckDB, no AWS account):
generate a simulated week, run the allocation pipeline, answer the CFO from cold,
reconcile, and watch the anomaly layer catch the planted retry loop.

    python labs/ch06/run_local.py
"""
import json
import pathlib
import sys
import tempfile
import time

LAB = pathlib.Path(__file__).resolve().parent
ROOT = LAB.parents[1]
sys.path.insert(0, str(ROOT / "finops" / "lib"))
sys.path.insert(0, str(LAB))
import anomaly  # noqa: E402
import generate  # noqa: E402
import pipeline  # noqa: E402


def main():
    data = pathlib.Path(tempfile.mkdtemp(prefix="ch06-"))
    print("step 5  synthetic week:", generate.generate(data))
    con = pipeline.duckdb_connect(data)
    print("        allocation steps (ms):", pipeline.run_duckdb(con, "2026-05"))
    t0 = time.perf_counter()
    rows = con.execute((LAB / "queries" / "feature_cost.sql").read_text()).fetchall()
    print(f"step 6  feature_cost.sql answered in {(time.perf_counter() - t0) * 1000:.0f} ms (target: < 60 s)")
    for f, cost, per in rows:
        print(f"        {f:<16} ${float(cost):>10,.2f}   per conversation {"—" if per is None else f"${float(per):.4f}"}")
    sql = pipeline.render((ROOT / "finops" / "queries" / "reconciliation.sql").read_text(), pipeline.params("2026-05"))
    print("step 7  reconciliation:")
    for bucket, amount, action in con.execute(sql).fetchall():
        print(f"        {bucket:<24} ${amount:>9,.2f}  → {action}")
    events = [json.loads(l) for l in (data / "gateway_events.jsonl").read_text().splitlines()]
    pages = anomaly.detect(events)
    print("step 8  anomaly layer:")
    print("        " + (min(pages, key=lambda p: p.hour).text() if pages else "NO PAGE — check the detector"))
    sys.exit(0 if pages and rows else 1)


if __name__ == "__main__":
    main()
