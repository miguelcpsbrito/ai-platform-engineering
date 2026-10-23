"""labs/ch12 — agent readiness drills, local mode: a runaway stopped by its budget, a
consequential action blocked without an approval the agent cannot produce, and both
kill switches pulled mid-trajectory. Reasoning calls go through the local gateway, so
spend is metered exactly as on AWS.
"""
import os
import pathlib
import socket
import subprocess
import sys
import time
import urllib.request

LAB = pathlib.Path(__file__).resolve().parent
ROOT = LAB.parents[1]
for p in ("agents", "observability"):
    sys.path.insert(0, str(ROOT / p))
from platform_agents import (ApprovalRequired, ApprovalService, BudgetExceeded, KillSwitch, Killed,  # noqa: E402
                             Registry, Runtime, Task, TaskBudget)
from platform_sdk import Context, Gateway  # noqa: E402


def start_gateway():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    env = dict(os.environ, PYTHONPATH=str(ROOT / "gateway"), PLATFORM_METERING_SINK="memory")
    p = subprocess.Popen([sys.executable, "-m", "platform_gateway.server", "--mock", "--env", "local",
                          "--port", str(port)], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    url = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            urllib.request.urlopen(url + "/healthz", timeout=1)
            return p, url
        except OSError:
            time.sleep(0.1)


def main():
    proc, url = start_gateway()
    prices = {"model-a": {"input": 3.0, "output": 15.0}}
    gw = Gateway(url, "lab-key-tenant-b", Context("cx-support", "refunds-agent"), prices=prices)
    tools = {"orders.lookup": lambda order_id: {"error": "malformed upstream response"},   # the bad tool
             "refunds.issue": lambda order_id, amount_usd: {"refund": order_id, "amount": amount_usd}}
    rt = Runtime(Registry(), KillSwitch(), ApprovalService(os.urandom(32)), tools)
    ok = True
    try:
        # act 1 — the runaway of the Chapter 12 war story, with a per-task budget this time
        t = Task("refunds-agent", "cx-support", 2, "task-runaway", "u-42", TaskBudget(max_steps=24, max_usd=0.25))
        rt.start(t)
        outcome = "ran forever"
        try:
            while True:
                plan = gw.chat([{"role": "user", "content": f"re-plan step {t.budget.steps}: order 1182 lookup failed"}])
                rt.call_tool(t, "orders.lookup", {"order_id": "1182"}, step_cost_usd=plan.cost_usd or 0.0)
        except BudgetExceeded as e:
            outcome = f"stopped: {e} after {t.budget.steps} steps, ${t.budget.spent_usd:.4f}"
        print(f"ACT 1  runaway → {outcome}")
        ok &= outcome.startswith("stopped")
        # act 2 — the consequential tool, without and with a human approval
        t2 = Task("refunds-agent", "cx-support", 2, "task-refund", "u-42", TaskBudget(10, 1.0))
        try:
            rt.call_tool(t2, "refunds.issue", {"order_id": "1182", "amount_usd": 40})
            print("ACT 2  FAIL refund issued without approval"); ok = False
        except ApprovalRequired as e:
            print(f"ACT 2  blocked → {e}")
        approval = rt.approvals.approve("refunds.issue", {"order_id": "1182", "amount_usd": 40}, "alice@payments")
        r = rt.call_tool(t2, "refunds.issue", {"order_id": "1182", "amount_usd": 40}, approval=approval)
        print(f"       approved by alice@payments → {r}")
        # act 3 — kill switches: halt in-flight at the next step boundary, then new starts
        t3 = Task("refunds-agent", "cx-support", 2, "task-inflight", "u-7", TaskBudget(50, 5.0))
        rt.start(t3)
        rt.call_tool(t3, "orders.lookup", {"order_id": "77"})
        rt.kill.pull("agent:refunds-agent")
        for label, fn in (("in-flight step", lambda: rt.call_tool(t3, "orders.lookup", {"order_id": "77"})),
                          ("new task start", lambda: rt.start(Task("refunds-agent", "cx-support", 2, "t4", "u", TaskBudget(5, 1))))):
            try:
                fn(); print(f"ACT 3  FAIL {label} not stopped"); ok = False
            except Killed as e:
                print(f"ACT 3  {label} → {e}")
        print(f"\naudit trail: {len(rt.audit)} tool calls recorded with task, user, class, step and spend")
    finally:
        proc.terminate()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
