"""Chapter 12's controls as tests: registry policy, budgets, kill switches, approvals the
agent cannot forge, and task-scoped credentials valid against the real STS model."""
import datetime as dt
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from platform_agents import (ApprovalRequired, ApprovalService, BudgetExceeded, KillSwitch, Killed,  # noqa: E402
                             PolicyDenied, Registry, Runtime, Task, TaskBudget)
from platform_agents.credentials import session_policy_for, task_credentials  # noqa: E402

REFUND = {"order_id": "1182", "amount_usd": 40}


@pytest.fixture
def rt():
    tools = {"orders.lookup": lambda order_id: {"order": order_id, "status": "delivered"},
             "refunds.issue": lambda order_id, amount_usd: {"refund": order_id, "amount": amount_usd}}
    return Runtime(Registry(), KillSwitch(), ApprovalService(b"channel-secret"), tools)


def task(tenant="cx-support", tier=2, steps=20, usd=1.0):
    return Task("refunds-agent", tenant, tier, "t-1", "u-42", TaskBudget(steps, usd))


def test_registry_entries_of_figure_12_2_load():
    r = Registry()
    assert r.tools["orders.lookup"].action_class == "read"
    assert r.tools["refunds.issue"].action_class == "consequential" and not r.tools["refunds.issue"].reversible


def test_tenant_outside_allow_list_is_denied(rt):
    with pytest.raises(PolicyDenied):
        rt.call_tool(task(tenant="marketing"), "orders.lookup", {"order_id": "1"})


def test_unregistered_tool_is_denied(rt):
    with pytest.raises(PolicyDenied):
        rt.call_tool(task(), "db.drop_table", {})


def test_runaway_is_stopped_by_the_step_budget(rt):
    """The I-3 war story: a loop that re-plans and re-calls. The budget ends it."""
    t = task(steps=50, usd=100)
    with pytest.raises(BudgetExceeded):
        for _ in range(1000):
            rt.call_tool(t, "orders.lookup", {"order_id": "1182"}, step_cost_usd=0.01)
    assert t.budget.steps <= 51


def test_per_task_tool_limit(rt):
    t = task(steps=100, usd=100)
    for _ in range(10):
        rt.call_tool(t, "orders.lookup", {"order_id": "1182"})
    with pytest.raises(BudgetExceeded, match="per-task limit"):
        rt.call_tool(t, "orders.lookup", {"order_id": "1182"})


def test_spend_budget(rt):
    with pytest.raises(BudgetExceeded, match="spend"):
        rt.call_tool(task(usd=0.05), "orders.lookup", {"order_id": "1"}, step_cost_usd=0.06)


def test_consequential_action_requires_approval_the_agent_cannot_forge(rt):
    t = task()
    with pytest.raises(ApprovalRequired):
        rt.call_tool(t, "refunds.issue", REFUND)
    forged = ApprovalService(b"agent-guess").approve("refunds.issue", REFUND, "agent")
    with pytest.raises(ApprovalRequired):
        rt.call_tool(t, "refunds.issue", REFUND, approval=forged)
    real = rt.approvals.approve("refunds.issue", REFUND, "alice@payments")
    with pytest.raises(ApprovalRequired):        # approval is bound to the exact arguments
        rt.call_tool(t, "refunds.issue", dict(REFUND, amount_usd=400), approval=real)
    assert rt.call_tool(t, "refunds.issue", REFUND, approval=real)["amount"] == 40


def test_kill_switch_halts_starts_and_inflight(rt):
    t = task()
    rt.start(t)
    rt.call_tool(t, "orders.lookup", {"order_id": "1"})
    rt.kill.pull("agent:refunds-agent")
    with pytest.raises(Killed):
        rt.call_tool(t, "orders.lookup", {"order_id": "1"})
    with pytest.raises(Killed):
        rt.start(task())
    rt.kill.reset("agent:refunds-agent")
    rt.start(task())


def test_task_credentials_request_is_valid_for_sts():
    import boto3
    from botocore.stub import Stubber
    sts = boto3.client("sts", region_name="us-east-1", aws_access_key_id="x", aws_secret_access_key="x")
    stub = Stubber(sts)
    import json
    expected = {"RoleArn": "arn:aws:iam::111122223333:role/agent-task-refunds",
                "RoleSessionName": "agent-refunds-agent-t-1", "DurationSeconds": 900,
                "Policy": json.dumps(session_policy_for(["orders.lookup"])),
                "Tags": [{"Key": "delegated-user", "Value": "u-42"}, {"Key": "task-id", "Value": "t-1"},
                         {"Key": "agent", "Value": "refunds-agent"}]}
    stub.add_response("assume_role", {"Credentials": {"AccessKeyId": "AKIAEXAMPLEEXAMPLE12", "SecretAccessKey": "s" * 40,
                                                      "SessionToken": "t", "Expiration": dt.datetime(2026, 10, 1)}},
                      expected)
    with stub:
        c = task_credentials(expected["RoleArn"], "refunds-agent", "t-1", "u-42", ["orders.lookup"], sts=sts)
    assert c["SessionToken"] == "t"
    assert session_policy_for(["orders.lookup"])["Statement"][0]["Effect"] == "Deny"   # no AWS-touching tools
