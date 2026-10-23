"""Governance as running code (Chapter 10): intake tiering, the data-class matrix, the
three guardrail layers with a red-team scorecard, the subject-deletion pipeline with its
completion report, and the audit record and drill."""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import re
import time
from dataclasses import dataclass, field

import yaml

GOV = pathlib.Path(__file__).resolve().parents[1]
ROOT = GOV.parent

# --- intake tiering (Figure 10.2) ----------------------------------------------------------


def classify(use_case: dict, rules_path: pathlib.Path = GOV / "intake" / "tiering.yaml") -> dict:
    """First matching rule wins; the most demanding tiers are listed first."""
    rules = yaml.safe_load(rules_path.read_text())
    for rule in rules["rules"]:
        if rule.get("default") or any(all(use_case.get(k) == v for k, v in cond.items())
                                      for cond in rule.get("when_any", [])):
            tier = rule["tier"]
            return {"tier": tier, "rules_version": rules["version"], "controls": rules["controls"][tier]}
    raise ValueError("tiering rules have no default")


# --- the data-class matrix (Section 10.3) ------------------------------------------------------

def matrix_decision(alias: str, data_class: str, contracts_dir: pathlib.Path = ROOT / "gateway" / "contracts") -> str:
    c = yaml.safe_load((contracts_dir / f"{alias}.yaml").read_text())
    return "allowed" if data_class in c.get("data_classes_allowed", []) else "blocked"


# --- three guardrail layers (Section 10.2) -------------------------------------------------------

class LocalLayer1:
    """Stand-in for a Bedrock guardrail profile in local mode: prompt-attack phrases and
    PII/secret patterns. It is deliberately about as strong as a default profile — it
    misses translated and hidden injections, which the corpus marks as known gaps."""
    ATTACK = re.compile(r"ignore (all )?(previous|prior) instructions|disregard your rules|you are now dan", re.I)
    PII = re.compile(r"\b\d{3}-\d{2}-\d{4}\b|\b(?:\d[ -]?){13,16}\b|[\w.+-]+@[\w-]+\.[\w.]+|\+?\d[\d ]{9,}\d|AKIA[0-9A-Z]{16}")

    def check(self, text: str, direction: str) -> str | None:
        if direction == "input" and self.ATTACK.search(text):
            return "PROMPT_ATTACK"
        if direction in ("output", "retrieved") and self.PII.search(text):
            return "PII"
        return None


class BedrockLayer1:
    """The real layer 1: ApplyGuardrail against the tier's profile."""

    def __init__(self, guardrail_id: str, version: str, client=None):
        import boto3
        self.id, self.version = guardrail_id, version
        self.client = client or boto3.client("bedrock-runtime")

    def check(self, text: str, direction: str) -> str | None:
        r = self.client.apply_guardrail(guardrailIdentifier=self.id, guardrailVersion=self.version,
                                        source="INPUT" if direction != "output" else "OUTPUT",
                                        content=[{"text": {"text": text}}])
        return "GUARDRAIL_INTERVENED" if r["action"] == "GUARDRAIL_INTERVENED" else None


class CompanyRules:
    """Layer 2: the company's own rules, which no vendor profile knows."""
    RULES = [
        ("no-competitor-advice", re.compile(r"\b(globex|initech)\b.*\b(cheaper|switch)\b", re.I)),
        ("no-guarantees", re.compile(r"\bguarantee\b.*\b(approved|refund|claim)\b", re.I)),
        ("no-exfiltration", re.compile(r"\b(e-?mail|send|post)\b.*\b(customer list|all customers)\b", re.I)),
        ("no-instruction-smuggling", re.compile(r"ignorez les consignes|révélez le prompt|follow the (\w+ )?text", re.I)),
    ]

    def check(self, text: str, direction: str) -> str | None:
        for name, rx in self.RULES:
            if rx.search(text):
                return name
        return None


class OutputContract:
    """Layer 3: the service's output contract — JSON with answer + citations only, no
    markup that a downstream renderer could execute."""

    def check(self, text: str, direction: str) -> str | None:
        if direction != "output":
            return None
        if re.search(r"<\s*script|javascript:|onerror\s*=", text, re.I):
            return "executable-markup"
        if text.strip().startswith("{"):
            try:
                doc = json.loads(text)
            except json.JSONDecodeError:
                return "invalid-json"
            if set(doc) - {"answer", "citations"}:
                return "unexpected-fields"
        return None


@dataclass
class Scorecard:
    rows: list[dict] = field(default_factory=list)

    def by_family(self) -> dict:
        out: dict = {}
        for r in self.rows:
            f = out.setdefault(r["family"], {"cases": 0, "blocked": 0, "missed": [], "false_positive": []})
            f["cases"] += 1
            if r["blocked_at"]:
                f["blocked"] += 1
            if r["expect_block_at"] != "none" and not r["blocked_at"]:
                f["missed"].append(r["id"])
            if r["expect_block_at"] == "none" and r["blocked_at"]:
                f["false_positive"].append(r["id"])
        for f in out.values():
            f["pass_rate"] = round(f["blocked"] / f["cases"], 3) if f["cases"] else None
        return out


def run_redteam(layers: list, corpus_path: pathlib.Path = GOV / "redteam" / "corpus.yaml") -> Scorecard:
    corpus = yaml.safe_load(corpus_path.read_text())
    sc = Scorecard()
    for case in corpus["cases"]:
        blocked_at, reason = None, None
        for i, layer in enumerate(layers, start=1):
            reason = layer.check(case["text"], case["layer"])
            if reason:
                blocked_at = i
                break
        sc.rows.append({"id": case["id"], "family": case["family"], "expect_block_at": case["expect_block_at"],
                        "blocked_at": blocked_at, "reason": reason, "known_gap": case.get("known_gap")})
    return sc


# --- subject deletion (Section 10.6, Table 5.7) ---------------------------------------------------

class Store:
    name = "store"

    def delete_subject(self, tenant: str, subject: str) -> int: ...
    def hunt(self, tenant: str, subject: str) -> int: ...


@dataclass
class DeletionReport:
    request_id: str
    tenant: str
    subject_ref: str
    started: str
    stores: list[dict]
    complete: bool

    def to_json(self) -> str:
        return json.dumps(self.__dict__, indent=2)


def delete_subject(stores: list[Store], tenant: str, subject: str, request_id: str,
                   backup_policy: str = "backups expire per policy BK-2 within 35 days") -> DeletionReport:
    started = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    rows = []
    for s in stores:
        deleted = s.delete_subject(tenant, subject)
        remaining = s.hunt(tenant, subject)
        rows.append({"store": s.name, "deleted": deleted, "verified_remaining": remaining,
                     "verification": "hunt query returned zero" if remaining == 0 else "RESIDUE FOUND"})
    rows.append({"store": "backups", "deleted": None, "verified_remaining": None, "verification": backup_policy})
    # the report never contains the subject identifier itself, only a reference
    ref = "sha256:" + __import__("hashlib").sha256(subject.encode()).hexdigest()[:16]
    return DeletionReport(request_id, tenant, ref, started, rows,
                          complete=all(r["verified_remaining"] in (0, None) for r in rows))


# --- the audit record and the audit drill (Section 10.4, Figure 10.5) --------------------------------

AUDIT_FIELDS = ["ts", "trace_id", "tenant", "workload_role", "feature", "risk_tier", "alias", "model",
                "config_version", "data_class", "matrix_decision", "guardrail", "tokens", "cost_usd"]


def audit_record(event: dict, tenant_rec: dict, data_class: str, guardrail: dict, content_ref: str | None = None) -> dict:
    rec = {"ts": event["ts"], "trace_id": event["trace_id"], "tenant": event["tenant"],
           "workload_role": (tenant_rec.get("identity") or {}).get("pod_identity_role")
           or (tenant_rec.get("identity") or {}).get("workload_role"),
           "feature": event["feature"], "risk_tier": tenant_rec.get("risk_tier", 1), "alias": event["alias"],
           "model": event["model"], "config_version": event["config_version"], "data_class": data_class,
           "matrix_decision": matrix_decision(event["alias"], data_class) if event.get("alias") else "n/a",
           "guardrail": guardrail, "tokens": {"in": event["tokens_in"], "out": event["tokens_out"]},
           "cost_usd": event["cost_usd"]}
    if content_ref:
        rec["content_ref"] = content_ref
    return rec


def audit_drill(events: list[dict], tenant: str, day: str) -> tuple[list[dict], float]:
    """Produce every interaction record for one tenant and day; return records and seconds."""
    t0 = time.perf_counter()
    out = [e for e in events if e["tenant"] == tenant and e["ts"].startswith(day)]
    return out, time.perf_counter() - t0
