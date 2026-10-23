"""A small, deliberately strict evaluator for Deny statements in SCPs.

It implements the subset of IAM policy grammar the repository's SCPs use, with AWS
semantics for missing keys: negated operators (StringNotEquals, StringNotLike,
ArnNotLike) match when the key is absent; positive operators do not; Null tests
presence. Keys inside one operator are ANDed, operators inside one Condition are
ANDed, values inside one key are ORed.

This is a unit-test oracle, not a replacement for the IAM policy simulator or for
the scheduled SCP suite that runs real calls in the test OU (Appendix A, Table A.3).
"""
from __future__ import annotations

import fnmatch
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]


def render_tftpl(text: str, variables: dict) -> str:
    """Render the two template forms the SCP templates use: ${jsonencode(x)} and ${x}."""
    def sub(m: re.Match) -> str:
        expr = m.group(1).strip()
        j = re.fullmatch(r"jsonencode\(([a-z_]+)\)", expr)
        if j:
            return json.dumps(variables[j.group(1)])
        return str(variables[expr])
    return re.sub(r"\$\{([^}]+)\}", sub, text)


def load_policy(path: str | pathlib.Path, variables: dict) -> dict:
    return json.loads(render_tftpl(pathlib.Path(path).read_text(), variables))


def _as_list(v):
    return v if isinstance(v, list) else [v]


def _like(value: str, pattern: str) -> bool:
    return fnmatch.fnmatchcase(value, pattern)


def _action_matches(action: str, patterns) -> bool:
    a = action.lower()
    return any(_like(a, p.lower()) for p in _as_list(patterns))


def _op(op: str, key: str, expected, ctx: dict) -> bool:
    expected = [str(e) for e in _as_list(expected)]
    qualifier = None
    if ":" in op and op.split(":")[0] in ("ForAnyValue", "ForAllValues"):
        qualifier, op = op.split(":", 1)
    present = key in ctx
    if op == "Null":
        want_null = expected[0] == "true"
        return (not present) == want_null
    values = [str(v) for v in _as_list(ctx[key])] if present else []
    negated = "Not" in op
    base = op.replace("Not", "")
    if base in ("StringEquals",):
        test = lambda v: v in expected
    elif base in ("StringLike", "ArnLike"):
        test = lambda v: any(_like(v, e) for e in expected)
    elif base == "Bool":
        test = lambda v: v.lower() in [e.lower() for e in expected]
    else:
        raise ValueError(f"operator not supported by the oracle: {op}")
    if qualifier == "ForAnyValue":
        hit = any(test(v) for v in values)
    elif qualifier == "ForAllValues":
        hit = all(test(v) for v in values)
    else:
        if not present:
            return negated  # AWS: negated operators match an absent key
        hit = any(test(v) for v in values)
    return (not hit) if negated else hit


def statement_denies(stmt: dict, action: str, ctx: dict) -> bool:
    assert stmt["Effect"] == "Deny", "the oracle evaluates Deny statements only"
    if "Action" in stmt and not _action_matches(action, stmt["Action"]):
        return False
    if "NotAction" in stmt and _action_matches(action, stmt["NotAction"]):
        return False
    for op, kv in stmt.get("Condition", {}).items():
        for key, expected in kv.items():
            if not _op(op, key, expected, ctx):
                return False
    return True


def denied_by(policy: dict, action: str, ctx: dict) -> list[str]:
    """Return the Sids of the statements that deny this request (empty = not denied)."""
    return [s.get("Sid", "?") for s in policy["Statement"] if statement_denies(s, action, ctx)]
