"""Spend-anomaly detection on gateway events (Section 6.6): hourly burn per tenant and
feature against a robust trailing baseline. A page names the tenant, the feature and the
hourly burn — the three facts the on-call needs before anything else.
"""
from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import dataclass


@dataclass
class Page:
    tenant: str
    feature: str
    hour: str
    hourly_burn_usd: float
    baseline_usd: float
    ratio: float
    calls: int
    top_convo_share: float

    def text(self) -> str:
        hint = (f"; {self.top_convo_share:.0%} of calls share one conversation — retry loop?"
                if self.top_convo_share > 0.5 else "")
        return (f"PAGE ai-spend tenant={self.tenant} feature={self.feature} hour={self.hour} "
                f"hourly_burn=${self.hourly_burn_usd:,.2f} ({self.ratio:.1f}x baseline "
                f"${self.baseline_usd:,.2f}){hint}")


def hourly(events):
    burn = defaultdict(float)
    calls = defaultdict(int)
    convos = defaultdict(lambda: defaultdict(int))
    for e in events:
        if e.get("status") != 200:
            continue
        k = (e["tenant"], e["feature"], e["ts"][:13])
        burn[k] += e["cost_usd"] or 0.0
        calls[k] += 1
        convos[k][e.get("convo_id")] += 1
    return burn, calls, convos


def detect(events, ratio: float = 5.0, min_usd: float = 1.0, history_hours: int = 72,
           declared_jobs: set | None = None) -> list[Page]:
    """Flag hours whose burn exceeds `ratio` x the median of the same series' previous
    `history_hours` hours (and an absolute floor, so idle features do not page).
    Spend from declared batch jobs (tenant, feature) is ignored: a nightly backfill is
    not an anomaly (Section 6.6)."""
    declared = declared_jobs or set()
    events = [e for e in events if (e["tenant"], e["feature"]) not in declared]
    burn, calls, convos = hourly(events)
    series = defaultdict(list)
    for (t, f, h), v in sorted(burn.items(), key=lambda kv: kv[0][2]):
        series[(t, f)].append((h, v))
    pages = []
    for (t, f), pts in series.items():
        for i, (h, v) in enumerate(pts):
            hist = [x for _, x in pts[max(0, i - history_hours):i]]
            if len(hist) < 24:
                continue
            base = statistics.median(hist)
            if v >= min_usd and base > 0 and v / base >= ratio:
                c = convos[(t, f, h)]
                pages.append(Page(t, f, h, round(v, 2), round(base, 2), v / base, calls[(t, f, h)],
                                  max(c.values()) / sum(c.values())))
    return pages
