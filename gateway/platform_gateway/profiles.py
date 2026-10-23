"""List the application inference profiles the gateway needs: one per tenant, model and
region in every resolution chain (Section 4.4 — the profile is the tenant's cost identity).

    python -m platform_gateway.profiles --env prod > ../terraform/profiles/profiles.auto.tfvars.json
"""
from __future__ import annotations

import argparse
import json
import sys

from .config import GATEWAY_DIR, Config, NotEntitled


def required_profiles(cfg: Config) -> list[dict]:
    seen, out = set(), []
    for t in sorted(cfg.tenants.values(), key=lambda x: x.tenant):
        cost_center = t.raw.get("cost_center", t.tenant)
        for alias in t.aliases:
            try:
                chain = cfg.resolve(alias, t)
            except NotEntitled:
                continue
            for target in chain:
                if target.provider != "bedrock":
                    continue
                key = f"{t.tenant}|{target.model}|{target.region}"
                if key in seen:
                    continue
                seen.add(key)
                out.append({"key": key, "tenant": t.tenant, "model": target.model,
                            "region": target.region, "cost_center": cost_center,
                            "name": f"{t.tenant}-{target.model.split('.')[-1].split(':')[0]}-{target.region}"[:64]})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default="prod")
    a = ap.parse_args()
    cfg = Config.load(GATEWAY_DIR, environment=a.env)
    json.dump({"profiles": required_profiles(cfg)}, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
