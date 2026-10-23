"""The evaluation harness (Sections 8.4 and 9.5): sampled level-3 evaluation, a
regression detector that alarms against baseline with trace IDs attached, judge
calibration against a human-labelled golden set, and the offline suite runner the
blueprint pipeline uses as its quality gate (Figure 7.9).
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import statistics
from dataclasses import dataclass, field

import yaml


# --- judges ----------------------------------------------------------------------------

class MockJudge:
    """Deterministic judge for local labs: reads the quality marker the mock models emit.
    It stands in for a model judge; it is not one, and the lab says so."""
    SCORES = {"strongest": 0.97, "strong": 0.94, "adequate": 0.80, "weak": 0.45}

    def score(self, question: str, answer: str, context: str = "", criterion: str = "grounding") -> float:
        m = re.search(r"\[[\w-]+:(\w+)\]", answer)
        base = self.SCORES.get(m.group(1), 0.5) if m else 0.5
        jitter = (int(hashlib.sha256((answer + criterion).encode()).hexdigest()[:4], 16) / 65535 - 0.5) * 0.06
        return max(0.0, min(1.0, base + jitter))


class GatewayJudge:
    """A model judge called through the platform like any tenant (Section 9.5: its own
    quota and floor). Returns a 0..1 score parsed from strict JSON."""

    def __init__(self, gateway, alias: str = "standard", rubric: str = ""):
        self.gw, self.alias, self.rubric = gateway, alias, rubric

    def score(self, question, answer, context="", criterion="grounding") -> float:
        prompt = (f"You are grading one answer. Criterion: {criterion}. {self.rubric}\n"
                  f"Question: {question}\nContext: {context}\nAnswer: {answer}\n"
                  'Reply with JSON only: {"score": <number between 0 and 1>}')
        r = self.gw.chat([{"role": "user", "content": prompt}], alias=self.alias, max_tokens=20)
        m = re.search(r"\{.*\}", r.text, re.S)
        return float(json.loads(m.group(0))["score"]) if m else float("nan")


# --- sampling ---------------------------------------------------------------------------

def sampled(trace_id: str, rate: float) -> bool:
    """Deterministic sampling by trace ID: the same interaction is in or out everywhere."""
    return int(hashlib.sha256(trace_id.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF < rate


# --- regression detection ---------------------------------------------------------------

@dataclass
class Alarm:
    criterion: str
    baseline_mean: float
    window_mean: float
    z: float
    n: int
    trace_ids: list[str]

    def text(self) -> str:
        return (f"QUALITY REGRESSION {self.criterion}: {self.window_mean:.2f} vs baseline "
                f"{self.baseline_mean:.2f} (z={self.z:.1f}, n={self.n}); traces: {', '.join(self.trace_ids[:3])}")


@dataclass
class RegressionDetector:
    """One-sided test of the recent window's mean against the baseline distribution.
    Alarms only with enough samples, so a single bad answer never pages."""
    baseline: list[float]
    criterion: str = "grounding"
    window: int = 20
    min_samples: int = 10
    z_threshold: float = 3.0
    min_low: int = 3            # samples clearly below baseline before an alarm
    recent: list[tuple[float, str]] = field(default_factory=list)

    def __post_init__(self):
        self.mu = statistics.fmean(self.baseline)
        self.sd = statistics.pstdev(self.baseline) or 0.05

    def observe(self, score: float, trace_id: str) -> Alarm | None:
        self.recent.append((score, trace_id))
        self.recent = self.recent[-self.window:]
        n = len(self.recent)
        if n < self.min_samples:
            return None
        m = statistics.fmean(s for s, _ in self.recent)
        z = (self.mu - m) / (self.sd / math.sqrt(n))
        low = sorted((s, t) for s, t in self.recent if s < self.mu - 2 * self.sd)
        if z >= self.z_threshold and len(low) >= self.min_low:
            return Alarm(self.criterion, self.mu, m, z, n, [t for _, t in low])
        return None


# --- calibration ------------------------------------------------------------------------

def calibration(judge_labels: list[bool], human_labels: list[bool]) -> dict:
    """Agreement and Cohen's kappa between judge pass/fail and human pass/fail."""
    assert len(judge_labels) == len(human_labels) and judge_labels
    n = len(judge_labels)
    agree = sum(j == h for j, h in zip(judge_labels, human_labels)) / n
    pj, ph = sum(judge_labels) / n, sum(human_labels) / n
    pe = pj * ph + (1 - pj) * (1 - ph)
    kappa = (agree - pe) / (1 - pe) if pe < 1 else 1.0
    return {"n": n, "agreement": round(agree, 3), "kappa": round(kappa, 3),
            "trust": "ok" if kappa >= 0.6 else "recalibrate"}


# --- the offline suite runner (blueprint quality gate) -----------------------------------

@dataclass
class CaseResult:
    id: str
    passed: bool
    checks: dict


def run_suite(suite_path: str, answer_fn, judge=None) -> dict:
    """Run an evaluation suite (Figure 7.9). answer_fn(question) -> (answer_text, citations).
    must_cite is checked mechanically; expect classes are checked with simple, explicit
    rules; the judge scores grounding where present."""
    suite = yaml.safe_load(open(suite_path))
    results, grounding = [], []
    for case in suite["cases"]:
        text, cites = answer_fn(case["question"])
        checks = {}
        if "must_cite" in case:
            checks["must_cite"] = all(c in cites for c in case["must_cite"])
        exp = case.get("expect")
        if exp == "polite_refusal":
            checks["refusal_ok"] = bool(re.search(r"\b(can't|cannot|unable|not able)\b", text, re.I))
        elif exp:
            checks["expect"] = True if not judge else judge.score(case["question"], text) >= 0.5
        if judge and case.get("expect") != "polite_refusal":
            g = judge.score(case["question"], text, criterion="grounding")
            grounding.append(g)
        results.append(CaseResult(case["id"], all(checks.values()), checks))
    th = suite.get("thresholds", {})
    refusal_cases = [r for r in results if "refusal_ok" in r.checks]
    summary = {
        "suite": suite["suite"],
        "passed_cases": sum(r.passed for r in results), "cases": len(results),
        "grounding": round(statistics.fmean(grounding), 3) if grounding else None,
        "refusal_ok": (sum(r.checks["refusal_ok"] for r in refusal_cases) / len(refusal_cases)) if refusal_cases else None,
        "results": [r.__dict__ for r in results],
    }
    gate = True
    if summary["grounding"] is not None and "grounding" in th:
        gate &= summary["grounding"] >= th["grounding"]
    if summary["refusal_ok"] is not None and "refusal_ok" in th:
        gate &= summary["refusal_ok"] >= th["refusal_ok"]
    gate &= all(r.checks.get("must_cite", True) for r in results)
    summary["gate"] = "pass" if gate else "fail"
    return summary
