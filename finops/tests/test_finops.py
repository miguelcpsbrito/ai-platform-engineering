"""The Chapter 6 pipeline on synthetic data: totals tie out to the CUR, every row is
reproducible, the rules do what Section 6.3 says, and the CFO's question is one query."""
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "finops" / "lib"))
sys.path.insert(0, str(ROOT / "labs" / "ch06"))
import anomaly  # noqa: E402
import generate  # noqa: E402
import pipeline  # noqa: E402
import weekly_message  # noqa: E402


@pytest.fixture(scope="module")
def data(tmp_path_factory):
    out = tmp_path_factory.mktemp("ch06")
    generate.generate(out)
    con = pipeline.duckdb_connect(out)
    pipeline.run_duckdb(con, "2026-05")
    return out, con


def q(con, sql):
    return con.execute(sql).fetchall()


def test_allocated_total_ties_out_to_the_cur(data):
    _, con = data
    cur = q(con, "SELECT SUM(cost_usd) FROM cur_normalized WHERE month='2026-05'")[0][0]
    alloc = float(q(con, "SELECT SUM(amount_usd) FROM allocated_costs WHERE month='2026-05'")[0][0])
    assert alloc == pytest.approx(cur, abs=0.05)


def test_every_row_names_its_rule(data):
    _, con = data
    assert q(con, "SELECT COUNT(*) FROM allocated_costs WHERE rule_version IS NULL OR rule_version = ''")[0][0] == 0


def test_idle_bar_charges_tenant_at_seventy_percent(data):
    _, con = data
    rows = dict(q(con, "SELECT tenant, SUM(amount_usd) FROM allocated_costs WHERE cost_type='capacity' GROUP BY 1"))
    total = float(rows["support-chatbot"] + rows["_platform_idle"])
    assert float(rows["support-chatbot"]) == pytest.approx(0.70 * total)   # utilization 55% < bar


def test_shared_pool_floor_and_proportional_split(data):
    _, con = data
    rows = dict(q(con, "SELECT tenant, SUM(amount_usd) FROM allocated_costs WHERE cost_type='allocation' "
                       "AND component='shared' GROUP BY 1"))
    assert all(float(v) >= 400 for v in rows.values())
    assert float(sum(rows.values())) == pytest.approx(2100.0, abs=0.01)


def test_cfo_question_is_one_query(data):
    _, con = data
    sql = (ROOT / "labs" / "ch06" / "queries" / "feature_cost.sql").read_text()
    rows = q(con, sql)
    features = {r[0] for r in rows}
    assert {"refund-flow", "order-status", "reserved-floor", "platform-share"} <= features
    refund = [r for r in rows if r[0] == "refund-flow"][0]
    assert refund[1] > 0 and refund[2] > 0          # cost and cost per conversation


def test_reconciliation_explains_drift_in_three_buckets(data):
    _, con = data
    sql = pipeline.render((ROOT / "finops" / "queries" / "reconciliation.sql").read_text(),
                          pipeline.params("2026-05"))
    rows = {r[0]: r[1] for r in q(con, sql)}
    assert set(rows) == {"price_table_drift", "untagged_or_ungoverned", "capacity_shaped"}
    assert rows["untagged_or_ungoverned"] == pytest.approx(35.70, abs=0.01)
    assert 0 < rows["price_table_drift"] < 10
    drift = float(q(con, "SELECT SUM(amount_usd) FROM allocated_costs WHERE feature='drift'")[0][0])
    assert drift == pytest.approx(rows["price_table_drift"] + rows["untagged_or_ungoverned"], abs=0.02)


def test_anomaly_alert_catches_the_planted_retry_loop(data):
    out, _ = data
    events = [json.loads(l) for l in (out / "gateway_events.jsonl").read_text().splitlines()]
    pages = anomaly.detect(events)
    assert pages, "the retry loop must page"
    assert {(p.tenant, p.feature) for p in pages} == {("support-chatbot", "refund-flow")}
    first = min(pages, key=lambda p: p.hour)
    assert first.hour == "2026-05-16T14" and "retry loop" in first.text()


def test_weekly_message_format():
    msg = weekly_message.render("warranty-assistant", 41, 1284, 1211, 0.27, 0.28, 3910, 6000, 5420,
                                ("warranty-answer", 1102), "prompt cache hit rate 81% → 86%",
                                "output tokens per answer +18% since Tue",
                                "https://ai.platform.internal/finops/warranty")
    assert msg.splitlines()[0] == "AI spend — warranty-assistant — week 41"
    assert "▲ 6% vs 4-week avg" in msg and "▼ 4%" in msg


def test_lever_ranking_orders_levers_per_feature(data):
    _, con = data
    sql = pipeline.render((ROOT / "finops" / "queries" / "lever_ranking.sql").read_text(), pipeline.params("2026-05"))
    rows = q(con, sql)
    first = {(r[0], r[1]): r[3] for r in rows if r[5] == 1}
    assert first[("cx-warranty", "claim-triage")] == "batch"            # declared latency-tolerant
    assert first[("support-chatbot", "refund-flow")] in ("prompt_caching", "output_discipline")


def test_declared_batch_job_does_not_page(data):
    out, _ = data
    events = [json.loads(l) for l in (out / "gateway_events.jsonl").read_text().splitlines()]
    assert anomaly.detect(events, declared_jobs={("support-chatbot", "refund-flow")}) == []


@pytest.mark.parametrize("name", ["executive", "finops", "tenant"])
def test_dashboard_queries_run(data, name):
    _, con = data
    sql = (ROOT / "finops" / "queries" / "dashboards" / f"{name}.sql").read_text()
    sql = sql.replace("{{month}}", "2026-05").replace("{{tenant}}", "support-chatbot")
    assert q(con, sql)
