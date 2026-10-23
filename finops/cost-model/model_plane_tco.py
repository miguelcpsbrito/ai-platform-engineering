"""Model-plane TCO calculator (Section 3.2, Figure 3.3): managed throughput vs self-hosting
at a given utilization, with the break-even utilization stated both with and without the
people who run the serving stack. Prices are inputs; the defaults are Atlas's symbolic,
October 2026 numbers.

    python finops/cost-model/model_plane_tco.py --tokens-b 2.1 --utilization 0.31
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass


@dataclass
class Inputs:
    tokens_b_per_month: float = 2.1          # billions of tokens actually used
    managed_monthly_usd: float = 42_000      # e.g. Bedrock provisioned, 2 model units
    instances: int = 4
    instance_hourly_usd: float = 16.288      # g5.48xlarge on-demand list, us-east-1
    hours_per_month: float = 730
    utilization: float = 0.31                # measured, not planned
    fte: float = 1.5
    fte_monthly_loaded_usd: float = 18_667   # ≈ $28k for 1.5 FTE


def compute(i: Inputs) -> dict:
    managed_per_m = i.managed_monthly_usd / (i.tokens_b_per_month * 1_000)
    hw = i.instances * i.instance_hourly_usd * i.hours_per_month
    people = i.fte * i.fte_monthly_loaded_usd
    capacity_b = i.tokens_b_per_month / i.utilization
    self_total = hw + people
    be_with = self_total / managed_per_m / 1_000          # billions of tokens to break even
    be_without = hw / managed_per_m / 1_000
    return {
        "managed_usd_per_1m": managed_per_m,
        "self_hw_usd": hw, "self_people_usd": people, "self_total_usd": self_total,
        "capacity_b": capacity_b,
        "self_vs_managed": (self_total / (i.tokens_b_per_month * 1_000)) / managed_per_m,
        "breakeven_b_with_fte": be_with, "breakeven_util_with_fte": be_with / capacity_b,
        "breakeven_b_without_fte": be_without, "breakeven_util_without_fte": be_without / capacity_b,
    }


def report(i: Inputs) -> str:
    r = compute(i)
    verdict = ("Neither condition held" if i.utilization < r["breakeven_util_without_fte"]
               else "Self-hosting breaks even only without counting people" if i.utilization < r["breakeven_util_with_fte"]
               else "Self-hosting breaks even")
    return "\n".join([
        f"Managed: ${i.managed_monthly_usd/1000:.0f}k / month → ${r['managed_usd_per_1m']:.0f} per 1M tokens",
        f"Self-hosted: {i.instances} instances ≈ ${r['self_hw_usd']/1000:.0f}k / month at list",
        f"  utilization {i.utilization:.0%} → capacity ≈ {r['capacity_b']:.1f}B tokens/month, "
        f"{i.tokens_b_per_month}B used",
        f"  + {i.fte} FTE ≈ ${r['self_people_usd']/1000:.0f}k → ${r['self_total_usd']/1000:.0f}k "
        f"≈ {r['self_vs_managed']:.1f}x managed per token",
        f"Break-even: with FTEs {r['breakeven_b_with_fte']:.2f}B tokens → ≥ {r['breakeven_util_with_fte']:.0%}; "
        f"without {r['breakeven_b_without_fte']:.2f}B → ≥ {r['breakeven_util_without_fte']:.0%}",
        f"{verdict} at {i.utilization:.0%}.",
    ])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    for f, v in Inputs().__dict__.items():
        ap.add_argument("--" + f.replace("_", "-"), type=type(v), default=v)
    a = ap.parse_args()
    print(report(Inputs(**{k.replace("-", "_"): v for k, v in vars(a).items()})))
