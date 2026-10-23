"""Synthetic multi-tenant traffic for the Chapter 6 lab: a simulated week in May 2026,
two tenants, four features, and one misbehaving retry loop hidden in the mix (Table 6.7,
step 5). Writes gateway events and a matching CUR extract with realistic gaps: a small
price-table drift, one untagged caller, a provisioned-throughput floor, vector indexes
and platform shared costs.

    python labs/ch06/generate.py --out labs/ch06/data
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import pathlib
import random
import sys
import uuid

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "gateway"))
from platform_gateway.config import Config, Target  # noqa: E402

FEATURES = {
    "support-chatbot": {"refund-flow": ("standard", 90), "order-status": ("fast", 160)},
    "cx-warranty": {"warranty-answer": ("standard", 70), "claim-triage": ("fast", 50)},
}
ACCOUNT = {"support-chatbot": "444455556666", "cx-warranty": "777788889999"}
RETRY_LOOP = {"tenant": "support-chatbot", "feature": "refund-flow", "day": 5, "hours": range(14, 18), "x": 40}
START = dt.date(2026, 5, 11)


def generate(out: pathlib.Path, seed: int = 42) -> dict:
    rng = random.Random(seed)
    cfg = Config.load(ROOT / "gateway", environment="prod")
    out.mkdir(parents=True, exist_ok=True)
    events, daily = [], {}
    for d in range(7):
        day = START + dt.timedelta(days=d)
        for tenant, feats in FEATURES.items():
            for feature, (alias, per_hour) in feats.items():
                target = cfg.resolve(alias, cfg.tenants[tenant])[0]
                for hour in range(24):
                    shape = 0.3 + 0.7 * (1 if 8 <= hour <= 20 else 0.2)
                    n = int(per_hour * shape * rng.uniform(0.85, 1.15))
                    loop = (tenant == RETRY_LOOP["tenant"] and feature == RETRY_LOOP["feature"]
                            and d == RETRY_LOOP["day"] and hour in RETRY_LOOP["hours"])
                    if loop:
                        n *= RETRY_LOOP["x"]
                    convos = [uuid.UUID(int=rng.getrandbits(128)).hex[:12] for _ in range(max(1, n // 4))]
                    for i in range(n):
                        tin = int(rng.gauss(1800 if alias == "standard" else 400, 200))
                        tout = int(rng.gauss(350 if alias == "standard" else 60, 40))
                        tin, tout = max(tin, 50), max(tout, 5)
                        cost = cfg.cost_usd(target, tin, tout)
                        ts = dt.datetime(day.year, day.month, day.day, hour, rng.randrange(60), rng.randrange(60),
                                         tzinfo=dt.timezone.utc)
                        events.append({
                            "ts": ts.isoformat(timespec="milliseconds"), "trace_id": uuid.UUID(int=rng.getrandbits(128)).hex,
                            "tenant": tenant, "feature": feature,
                            "convo_id": convos[0] if loop else rng.choice(convos),
                            "alias": alias, "provider": "bedrock", "model": target.model, "region": target.region,
                            "tier": target.tier, "status": 200, "fallback": False, "attempts": 1, "cache_hit": False,
                            "tokens_in": tin, "tokens_out": tout, "tokens_cached": 0, "cost_usd": cost,
                            "latency_ms": round(rng.uniform(300, 2500), 1), "config_version": "gw-2026.05.10-1",
                            "environment": "prod", "faults": None})
                        daily[(day, tenant)] = daily.get((day, tenant), 0.0) + cost
    events.sort(key=lambda e: e["ts"])
    with open(out / "gateway_events.jsonl", "w") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")

    rows = []
    for (day, tenant), cost in sorted(daily.items()):
        acct = ACCOUNT[tenant]
        # Invocation through the tenant's application profile; the CUR prices 1.2% higher.
        rows.append([day, acct, "AmazonBedrock", "USE1-MP:USE1_InputTokenCount-input-tokens",
                     f"arn:aws:bedrock:us-east-1:{acct}:application-inference-profile/{tenant[:8]}",
                     tenant, "cx", "", round(cost * 0.80 * 1.012, 6), "2026-05"])
        rows.append([day, acct, "AmazonBedrock", "USE1-MP:USE1_OutputTokenCount-output-tokens",
                     f"arn:aws:bedrock:us-east-1:{acct}:application-inference-profile/{tenant[:8]}",
                     tenant, "cx", "", round(cost * 0.20 * 1.012, 6), "2026-05"])
        rows.append([day, acct, "AmazonOpenSearchServerless", "USE1-SearchOCU", f"aoss-{tenant}",
                     tenant, "cx", "retrieval", 23.04, "2026-05"])
    for d in range(7):
        day = START + dt.timedelta(days=d)
        rows.append([day, "999900001111", "AmazonBedrock", "USE1-MP:USE1_InputTokenCount-input-tokens",
                     "", "", "", "", 5.10, "2026-05"])            # untagged caller: shadow AI
        rows.append([day, "444455556666", "AmazonBedrock", "USE1-ProvisionedThroughput-ModelUnitHours",
                     "arn:aws:bedrock:us-east-1:444455556666:provisioned-model/pt-support",
                     "support-chatbot", "cx", "", 480.0, "2026-05"])
        rows.append([day, "111122223333", "AmazonEKS", "USE1-AmazonEKS-Hours:perCluster", "platform-gateway",
                     "", "platform", "", 300.0, "2026-05"])
    with open(out / "cur_normalized.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["usage_date", "account_id", "service", "usage_type", "resource_id", "tag_tenant",
                    "tag_cost_center", "tag_feature", "cost_usd", "month"])
        w.writerows(rows)
    with open(out / "capacity_utilization.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["month", "resource_id", "tenant", "utilization"])
        w.writerow(["2026-05", "arn:aws:bedrock:us-east-1:444455556666:provisioned-model/pt-support",
                    "support-chatbot", 0.55])
    return {"events": len(events), "cur_rows": len(rows), "out": str(out)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(pathlib.Path(__file__).parent / "data"))
    print(generate(pathlib.Path(ap.parse_args().out)))
