"""The fault-injection layer (Sections 9.5 and 9.7): disabled by default, scriptable in
labs and game days, and impossible to leave on silently — every injected fault is
stamped on the metering event and the trace.

Rule fields:
  match       — "<model>@<region>", "<model>@*", "*@<region>" or "*"
  error_rate  — 0..1, probability of raising a retryable upstream error
  latency_ms  — added latency
  swap_to     — serve with a different model (a silent swap: Difference 4, Chapter 8)
  tenant      — optional; restrict the rule to one tenant
"""
from __future__ import annotations

import fnmatch
import json
import os
import random
import threading
import time
from dataclasses import dataclass, replace

from .backends import UpstreamError
from .config import Target


@dataclass
class FaultRule:
    match: str = "*"
    error_rate: float = 0.0
    latency_ms: int = 0
    swap_to: str | None = None
    tenant: str | None = None

    def applies(self, tenant: str, target: Target) -> bool:
        if self.tenant and self.tenant != tenant:
            return False
        return fnmatch.fnmatchcase(f"{target.model}@{target.region}", self.match)


class FaultLayer:
    def __init__(self, backend, rules: list[FaultRule] | None = None, seed: int = 7):
        self.backend = backend
        self.rules = rules or []
        self.rng = random.Random(seed)
        self.lock = threading.Lock()
        if not self.rules and os.environ.get("PLATFORM_FAULTS"):
            self.load(json.loads(os.environ["PLATFORM_FAULTS"]))

    def load(self, rules: list[dict]) -> None:
        with self.lock:
            self.rules = [FaultRule(**r) for r in rules]

    def clear(self) -> None:
        with self.lock:
            self.rules = []

    @property
    def active(self) -> bool:
        return bool(self.rules)

    def call(self, tenant, target: Target, messages, max_tokens, temperature=None):
        injected = []
        with self.lock:
            rules = [r for r in self.rules if r.applies(tenant.tenant, target)]
        for r in rules:
            if r.latency_ms:
                time.sleep(r.latency_ms / 1000)
                injected.append(f"latency:{r.latency_ms}")
            if r.error_rate and self.rng.random() < r.error_rate:
                raise UpstreamError(f"fault layer: injected failure on {target.label}",
                                    retryable=True, code="InjectedFault")
            if r.swap_to:
                injected.append(f"swap:{r.swap_to}")
                target = replace(target, model=r.swap_to)
        result = self.backend.call(tenant, target, messages, max_tokens, temperature)
        result.guardrail = dict(result.guardrail, faults=injected) if injected else result.guardrail
        return result
