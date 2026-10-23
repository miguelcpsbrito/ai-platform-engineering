"""Run the allocation pipeline (Section 6.5) on DuckDB (local labs, tests) or Athena.

    python finops/lib/pipeline.py --month 2026-05 --engine duckdb --data labs/ch06/data
"""
from __future__ import annotations

import argparse
import pathlib
import time

import yaml

FINOPS = pathlib.Path(__file__).resolve().parents[1]
STEPS = sorted((FINOPS / "allocation").glob("0*.sql"))


def params(month: str, rules: dict | None = None) -> dict:
    rules = rules or yaml.safe_load((FINOPS / "allocation" / "rules.yaml").read_text())
    def pred(kind, col="usage_type"):
        return "(" + " OR ".join(f"{col} LIKE '{p}'" for p in rules["patterns"][kind]) + ")"
    return {
        "month": month, "rule_version": rules["rule_version"], "idle_bar": rules["idle_bar"],
        "shared_floor_usd": rules["shared_floor_usd"], "platform_cost_center": rules["platform_cost_center"],
        "bedrock_service": rules["bedrock_service"],
        "invocation_predicate": pred("invocation"), "provisioned_predicate": pred("provisioned"),
        "provisioned_predicate_c": pred("provisioned", "c.usage_type"),
    }


def render(sql: str, p: dict) -> str:
    for k, v in p.items():
        sql = sql.replace("{{" + k + "}}", str(v))
    assert "{{" not in sql, f"unrendered placeholder in: {sql[:200]}"
    return sql


ALLOCATED_DDL = """CREATE TABLE IF NOT EXISTS allocated_costs (
  usage_date date, account_id varchar, tenant varchar, app varchar, feature varchar,
  alias varchar, component varchar, cost_type varchar, source varchar,
  amount_usd decimal(18,6), convo_id varchar, rule_version varchar, month varchar)"""


def duckdb_connect(data_dir: pathlib.Path):
    import duckdb
    con = duckdb.connect()
    con.execute("SET TimeZone = 'UTC'")
    # ts stays an ISO string, as in Athena; dt is the partition column Firehose writes.
    con.execute(f"""CREATE VIEW gateway_events AS
                    SELECT * REPLACE (strftime(ts, '%Y-%m-%dT%H:%M:%S.%g+00:00') AS ts),
                           strftime(ts, '%Y-%m-%d') AS dt
                    FROM read_json_auto('{data_dir / "gateway_events.jsonl"}')""")
    con.execute(f"CREATE VIEW cur_normalized AS SELECT * FROM read_csv_auto('{data_dir / 'cur_normalized.csv'}')")
    con.execute(f"CREATE VIEW capacity_utilization AS SELECT * FROM read_csv_auto('{data_dir / 'capacity_utilization.csv'}')")
    con.execute(ALLOCATED_DDL)
    # Athena addresses tables as finops.<table>; DuckDB gets the same names via a schema.
    con.execute("CREATE SCHEMA IF NOT EXISTS finops")
    con.execute("CREATE VIEW finops.allocated_costs AS SELECT * FROM main.allocated_costs")
    return con


def run_duckdb(con, month: str) -> dict:
    p = params(month)
    timings = {}
    con.execute("DELETE FROM allocated_costs WHERE month = ? AND rule_version = ?", [month, p["rule_version"]])
    for step in STEPS:
        t0 = time.perf_counter()
        con.execute(render(step.read_text(), p))
        timings[step.name] = round((time.perf_counter() - t0) * 1000, 1)
    return timings


def run_athena(month: str, workgroup: str, database: str = "finops") -> None:
    import boto3
    athena = boto3.client("athena")
    p = params(month)
    for step in STEPS:
        sql = render(step.read_text(), p).replace("INSERT INTO allocated_costs", "INSERT INTO finops.allocated_costs")
        qid = athena.start_query_execution(QueryString=sql, WorkGroup=workgroup,
                                           QueryExecutionContext={"Database": database})["QueryExecutionId"]
        while True:
            s = athena.get_query_execution(QueryExecutionId=qid)["QueryExecution"]["Status"]
            if s["State"] in ("SUCCEEDED", "FAILED", "CANCELLED"):
                break
            time.sleep(1)
        if s["State"] != "SUCCEEDED":
            raise SystemExit(f"{step.name}: {s.get('StateChangeReason')}")
        print(f"{step.name}: {s['State']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--month", required=True)
    ap.add_argument("--engine", choices=["duckdb", "athena"], default="duckdb")
    ap.add_argument("--data", default="labs/ch06/data")
    ap.add_argument("--workgroup", default="finops")
    a = ap.parse_args()
    if a.engine == "duckdb":
        con = duckdb_connect(pathlib.Path(a.data).resolve())
        print(run_duckdb(con, a.month))
        print(con.execute("SELECT cost_type, tenant, ROUND(SUM(amount_usd), 2) FROM allocated_costs "
                          "GROUP BY 1, 2 ORDER BY 1, 2").fetchall())
    else:
        run_athena(a.month, a.workgroup)
