"""The weekly message (Section 6.5, Figure 6.6): same format every week, which is why
people read it. Built from allocated costs and gateway events for one tenant."""
from __future__ import annotations


def render(tenant: str, week: int, spend: float, avg4: float, per_outcome: float, per_outcome_prev: float,
           mtd: float, budget: float, forecast: float, top_feature: tuple[str, float],
           top_change: str, look_closer: str, url: str) -> str:
    def arrow(now, before):
        if before == 0:
            return ""
        d = (now - before) / before
        return f"({'▲' if d >= 0 else '▼'} {abs(d):.0%}{' vs 4-week avg' if before == avg4 else ''})"
    lines = [
        f"AI spend — {tenant} — week {week}",
        f"  Spend          ${spend:,.0f}   {arrow(spend, avg4)}",
        f"  Per outcome    ${per_outcome:.2f} per resolved conversation {arrow(per_outcome, per_outcome_prev)}",
        f"  Month to date  ${mtd:,.0f} of ${budget:,.0f} budget — forecast ${forecast:,.0f}",
        f"  Top feature    {top_feature[0]}  ${top_feature[1]:,.0f}",
        f"  Top change     {top_change}",
        f"  Look closer    {look_closer}" if look_closer else "  Look closer    —",
        f"  Details        {url}",
    ]
    return "\n".join(lines)
