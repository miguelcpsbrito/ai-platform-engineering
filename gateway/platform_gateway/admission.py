"""Token-denominated quotas with two-phase accounting (Section 5.2, Figures 5.4 and 5.5).

The gateway cannot know a request's cost before it runs, so admission debits the worst
case (input estimate + max_tokens) and settlement credits back what was not used.
"""
from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass


def count_input(messages: list[dict]) -> int:
    """Cheap, deliberately pessimistic input-token estimate: ~4 characters per token."""
    chars = 0
    for m in messages:
        c = m.get("content", "")
        if isinstance(c, list):
            c = " ".join(part.get("text", "") for part in c if isinstance(part, dict))
        chars += len(str(c))
    return max(1, math.ceil(chars / 4)) + 4 * len(messages)


class TokenBucket:
    """Tokens-per-minute bucket with a burst allowance (default 2x for 60 seconds)."""

    def __init__(self, tokens_per_minute: int, burst_multiplier: float = 2.0, clock=time.monotonic):
        self.rate = tokens_per_minute / 60.0
        self.capacity = tokens_per_minute * burst_multiplier
        self.level = float(tokens_per_minute)  # start full at one minute, not at burst
        self.limit_value = tokens_per_minute
        self.clock = clock
        self.t = clock()
        self.lock = threading.Lock()
        self.debited_window: list[tuple[float, int]] = []

    def _refill(self) -> None:
        now = self.clock()
        self.level = min(self.capacity, self.level + (now - self.t) * self.rate)
        self.t = now

    def try_debit(self, n: int) -> bool:
        with self.lock:
            self._refill()
            if n <= self.level:
                self.level -= n
                self.debited_window.append((self.t, n))
                return True
            return False

    def credit(self, n: int) -> None:
        with self.lock:
            self._refill()
            self.level = min(self.capacity, self.level + max(n, 0))

    def eta(self, n: int) -> int:
        """Seconds until n tokens would be available (the Retry-After value)."""
        with self.lock:
            self._refill()
            missing = n - self.level
            return 0 if missing <= 0 else math.ceil(missing / self.rate) if self.rate else 60

    def current_window(self) -> int:
        """Tokens debited in the last 60 seconds — the 'current' field of a 429 body."""
        with self.lock:
            cutoff = self.clock() - 60
            self.debited_window = [(t, n) for t, n in self.debited_window if t >= cutoff]
            return sum(n for _, n in self.debited_window)


@dataclass
class Reservation:
    tenant: str
    est: int


@dataclass
class Rejection:
    status: int
    headers: dict
    body: dict


class QuotaExceeded(Exception):
    def __init__(self, rejection: Rejection):
        super().__init__(rejection.body["error"])
        self.rejection = rejection


class Admission:
    """Per-tenant buckets plus the 429 contract."""

    def __init__(self, tenants: dict, clock=time.monotonic,
                 raise_url: str = "https://ai.platform.internal/quota/raise"):
        self.raise_url = raise_url
        self.tenants = tenants
        self.bucket = {name: TokenBucket(t.tokens_per_minute, clock=clock)
                       for name, t in tenants.items() if t.tokens_per_minute}

    def admit(self, tenant, max_tokens: int, messages: list[dict], trace_id: str) -> Reservation:
        est = count_input(messages) + max_tokens          # worst case
        b = self.bucket.get(tenant.tenant)
        if b is None:                                     # no quota configured
            return Reservation(tenant.tenant, est)
        if not b.try_debit(est):
            wait = b.eta(est)
            raise QuotaExceeded(self.reject_429(tenant, b, est, wait, trace_id))
        return Reservation(tenant.tenant, est)

    def settle(self, res: Reservation, input_tokens: int, output_tokens: int) -> int:
        actual = input_tokens + output_tokens
        b = self.bucket.get(res.tenant)
        if b is not None:
            b.credit(res.est - actual)                    # give back unused
        return actual                                     # bill what happened

    def reject_429(self, tenant, b: TokenBucket, est: int, wait: int, trace_id: str) -> Rejection:
        return Rejection(
            status=429,
            headers={"Retry-After": str(max(wait, 1))},
            body={
                "error": "tenant_quota_exceeded",
                "limit": "tokens_per_minute", "window_s": 60,
                "limit_value": b.limit_value, "current": b.current_window() + est,
                "class": tenant.klass,
                "raise_request": self.raise_url,
                "trace_id": trace_id,
            },
        )
