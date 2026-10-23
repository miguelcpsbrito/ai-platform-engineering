"""Chapter 10 as tests: tiering, the matrix, layered guardrails against the red-team
corpus, plant–delete–hunt, and the audit record."""
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "governance"))
sys.path.insert(0, str(ROOT / "tenancy"))
import platform_governance as g  # noqa: E402
from platform_governance.stores import DictStore, IndexStore  # noqa: E402
from platform_retrieval import InMemoryIndex  # noqa: E402


@pytest.mark.parametrize("use_case,tier", [
    ({"data_class": "regulated"}, 3),
    ({"data_class": "internal", "decision_consequence": "consequential"}, 3),
    ({"data_class": "confidential"}, 2),
    ({"data_class": "internal", "tools_risk_class": "write"}, 2),
    ({"data_class": "internal", "audience": "employees"}, 1),
])
def test_tiering_first_match_wins(use_case, tier):
    r = g.classify(use_case)
    assert r["tier"] == tier and r["rules_version"] == 9
    if tier == 3:
        assert r["controls"]["dpia"] == "required" and r["controls"]["isolation_min_level"] == 3


def test_matrix_blocks_regulated_on_external_class_alias():
    assert g.matrix_decision("standard", "regulated") == "blocked"
    assert g.matrix_decision("standard", "confidential") == "allowed"
    assert g.matrix_decision("fast", "confidential") == "blocked"


@pytest.fixture(scope="module")
def scorecard():
    return g.run_redteam([g.LocalLayer1(), g.CompanyRules(), g.OutputContract()])


def test_every_expected_block_happens_at_or_before_its_layer(scorecard):
    for r in scorecard.rows:
        if r["expect_block_at"] == "none":
            assert r["blocked_at"] is None, f"false positive on {r['id']}: {r['reason']}"
        else:
            assert r["blocked_at"] is not None, f"{r['id']} got through every layer"
            assert r["blocked_at"] <= r["expect_block_at"], r


def test_known_gaps_are_real_gaps_of_layer_one_alone(scorecard):
    only_l1 = g.run_redteam([g.LocalLayer1()])
    gaps = {r["id"] for r in only_l1.rows if r["known_gap"] == "layer1"}
    assert gaps and all(r["blocked_at"] is None for r in only_l1.rows if r["id"] in gaps)
    assert all(r["blocked_at"] == 2 for r in scorecard.rows if r["id"] in gaps)


def test_scorecard_reports_per_family(scorecard):
    fam = scorecard.by_family()
    assert fam["LLM01-prompt-injection"]["pass_rate"] == 1.0
    assert fam["benign"]["false_positive"] == []


def test_plant_delete_hunt():
    subject = "Maria Example 4471"
    idx = InMemoryIndex()
    idx.add("t-a", "d1", f"Ticket from {subject}: refund for order 1182")
    idx.add("t-a", "d2", "Unrelated ticket about shipping")
    idx.add("t-b", "d3", f"Other tenant also mentions {subject}")       # must survive: other tenant
    cache = DictStore("exact-cache", {("t-a", "k1"): f"answer for {subject}", ("t-a", "k2"): "other"})
    logs = DictStore("prompt-logs", {("t-a", "l1"): f"prompt by {subject}"})
    rep = g.delete_subject([IndexStore(idx), cache, logs], "t-a", subject, "DSR-2026-0042")
    assert rep.complete
    assert [r["deleted"] for r in rep.stores[:3]] == [1, 1, 1]
    assert subject not in rep.to_json()                                 # the receipt carries a reference only
    assert any(subject in r[2] for r in idx.rows if r[0] == "t-b")


def test_audit_record_has_figure_10_5_fields():
    ev = {"ts": "2026-10-14T13:02:11.482Z", "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736", "tenant": "cx-warranty",
          "feature": "warranty-answer", "alias": "standard", "model": "us.anthropic.claude-sonnet-4-6",
          "config_version": "gw-2026.10.12-2", "tokens_in": 3812, "tokens_out": 241, "cost_usd": 0.0157}
    rec = g.audit_record(ev, {"risk_tier": 1, "identity": {"pod_identity_role": "arn:aws:iam::1:role/cx"}},
                         "confidential", {"profile": "tier1@v12", "input": "pass", "output": "masked:EMAIL"})
    assert list(rec) == g.AUDIT_FIELDS and rec["matrix_decision"] == "allowed"
