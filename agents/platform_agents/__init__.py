"""Agent primitives (Chapter 12): the tool registry and its usage policy, task budgets,
kill switches, approvals the agent cannot produce, and task-scoped credentials.
The runtime (AgentCore or your own loop) calls these at every step boundary."""
from __future__ import annotations

import hashlib
import hmac
import json
import pathlib
import threading
import time
from dataclasses import dataclass, field

import yaml

REGISTRY = pathlib.Path(__file__).resolve().parents[1] / "registry" / "tools.yaml"


class PolicyDenied(PermissionError):
    pass


class BudgetExceeded(RuntimeError):
    """A defined outcome, not a crash: checkpoint, summarize, hand to a human (12.4)."""


class Killed(RuntimeError):
    pass


class ApprovalRequired(PermissionError):
    pass


# --- registry ---------------------------------------------------------------------------

@dataclass
class Tool:
    name: str
    owner: str
    action_class: str
    reversible: bool
    spec: dict

    @property
    def per_task_limit(self) -> int | None:
        return (self.spec.get("rate_limit") or {}).get("per_task")


class Registry:
    def __init__(self, path: pathlib.Path = REGISTRY):
        self.tools: dict[str, Tool] = {}
        for doc in yaml.safe_load_all(path.read_text()):
            if not doc:
                continue
            if doc.get("kind") != "Tool":
                raise ValueError(f"unexpected kind {doc.get('kind')}")
            md, spec = doc["metadata"], doc["spec"]
            if spec.get("action_class") not in ("read", "write", "consequential"):
                raise ValueError(f"{md['name']}: action_class must be read | write | consequential")
            if spec["action_class"] == "consequential" and "approval" not in spec:
                raise ValueError(f"{md['name']}: consequential tools must declare an approval channel")
            self.tools[md["name"]] = Tool(md["name"], md["owner"], spec["action_class"],
                                          bool(spec.get("reversible", False)), spec)

    def check(self, tool: str, tenant: str, tier: int) -> Tool:
        t = self.tools.get(tool)
        if t is None:
            raise PolicyDenied(f"tool {tool!r} is not registered")
        tenants = t.spec.get("allowed_tenants")
        if tenants is not None and tenant not in tenants:
            raise PolicyDenied(f"tenant {tenant!r} may not use {tool}")
        tiers = t.spec.get("allowed_tiers")
        if tiers is not None and tier not in tiers:
            raise PolicyDenied(f"risk tier {tier} may not use {tool}")
        return t


# --- budgets and kill switches ------------------------------------------------------------

@dataclass
class TaskBudget:
    max_steps: int
    max_usd: float
    steps: int = 0
    spent_usd: float = 0.0
    tool_calls: dict = field(default_factory=dict)

    def charge_step(self, usd: float = 0.0) -> None:
        self.steps += 1
        self.spent_usd += usd
        if self.steps > self.max_steps:
            raise BudgetExceeded(f"step budget {self.max_steps} exhausted")
        if self.spent_usd > self.max_usd:
            raise BudgetExceeded(f"spend budget ${self.max_usd:.2f} exhausted (${self.spent_usd:.2f})")

    def charge_tool(self, tool: Tool) -> None:
        n = self.tool_calls.get(tool.name, 0) + 1
        self.tool_calls[tool.name] = n
        if tool.per_task_limit and n > tool.per_task_limit:
            raise BudgetExceeded(f"{tool.name}: per-task limit {tool.per_task_limit} exhausted")


class KillSwitch:
    """Two controls per agent deployment and per tenant: stop new task starts, and
    terminate in-flight trajectories at the next step boundary (12.4). Backed by a
    parameter store in production; in memory here."""

    def __init__(self):
        self._starts: set[str] = set()
        self._inflight: set[str] = set()
        self._lock = threading.Lock()

    def pull(self, scope: str, starts: bool = True, inflight: bool = True) -> None:
        with self._lock:
            if starts:
                self._starts.add(scope)
            if inflight:
                self._inflight.add(scope)

    def reset(self, scope: str) -> None:
        with self._lock:
            self._starts.discard(scope)
            self._inflight.discard(scope)

    def check_start(self, agent: str, tenant: str) -> None:
        if {f"agent:{agent}", f"tenant:{tenant}"} & self._starts:
            raise Killed("new task starts are halted")

    def check_step(self, agent: str, tenant: str) -> None:
        if {f"agent:{agent}", f"tenant:{tenant}"} & self._inflight:
            raise Killed("in-flight trajectories terminated at the step boundary")


# --- approvals the agent cannot produce ---------------------------------------------------

class ApprovalService:
    """Approvals are rendered from structured arguments and signed by the approval
    channel's key, which the agent runtime never holds (12.2)."""

    def __init__(self, channel_key: bytes):
        self._key = channel_key

    @staticmethod
    def render(tool: str, args: dict) -> str:
        return f"{tool} " + json.dumps(args, sort_keys=True)

    def approve(self, tool: str, args: dict, approver: str, ttl_s: int = 1800) -> dict:
        exp = int(time.time()) + ttl_s
        msg = f"{self.render(tool, args)}|{approver}|{exp}".encode()
        return {"approver": approver, "exp": exp, "sig": hmac.new(self._key, msg, hashlib.sha256).hexdigest()}

    def verify(self, tool: str, args: dict, approval: dict | None) -> None:
        if not approval:
            raise ApprovalRequired(f"{tool} requires approval: {self.render(tool, args)}")
        msg = f"{self.render(tool, args)}|{approval['approver']}|{approval['exp']}".encode()
        good = hmac.compare_digest(hmac.new(self._key, msg, hashlib.sha256).hexdigest(), approval.get("sig", ""))
        if not good or approval["exp"] < time.time():
            raise ApprovalRequired("approval invalid, expired, or for different arguments")


# --- the step boundary ------------------------------------------------------------------------

@dataclass
class Task:
    agent: str
    tenant: str
    tier: int
    task_id: str
    user_id: str
    budget: TaskBudget


class Runtime:
    """Everything a tool call must pass, in order, at every step."""

    def __init__(self, registry: Registry, kill: KillSwitch, approvals: ApprovalService, tools: dict):
        self.registry, self.kill, self.approvals, self.impl = registry, kill, approvals, tools
        self.audit: list[dict] = []

    def start(self, task: Task) -> None:
        self.kill.check_start(task.agent, task.tenant)

    def call_tool(self, task: Task, tool: str, args: dict, step_cost_usd: float = 0.0, approval: dict | None = None):
        self.kill.check_step(task.agent, task.tenant)
        task.budget.charge_step(step_cost_usd)
        t = self.registry.check(tool, task.tenant, task.tier)
        task.budget.charge_tool(t)
        if t.action_class == "consequential":
            self.approvals.verify(tool, args, approval)
        result = self.impl[tool](**args)
        self.audit.append({"task": task.task_id, "agent": task.agent, "user": task.user_id, "tool": tool,
                           "class": t.action_class, "step": task.budget.steps, "spent": round(task.budget.spent_usd, 4)})
        return result
