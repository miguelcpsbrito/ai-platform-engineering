"""Render the LiteLLM proxy configuration from the platform's own config (Section 4.5).

The alias map and tenant records stay the source of truth; the proxy's config is a build
artifact. Swapping the proxy for another product means writing another renderer, not
editing applications — the anti-lock-in rule of Section 4.7.

Mapping:
  alias × tenant      → one model group "<alias>--<tenant>" per target in the chain,
                        each calling the tenant's application inference profile (model_id)
  fallback chain      → router_settings.fallbacks
  tenant record       → a team: models, model_aliases (alias → tenant group), tpm, budget
  risk tier           → guardrailConfig on every deployment of that tenant

Known gap (October 2026, LiteLLM 1.79): Bedrock service tiers are not passed through, so
`tier` is recorded in model_info.platform_tier only. The custom gateway applies it (backends.py).

usage: python -m platform_gateway.render_litellm --env prod --profiles profiles.json --out build/
"""
from __future__ import annotations

import argparse
import json
import pathlib

import yaml

from .config import GATEWAY_DIR, Config, NotEntitled


def group(alias: str, tenant: str, i: int) -> str:
    return f"{alias}--{tenant}" if i == 0 else f"{alias}--{tenant}--fb{i}"


def render(cfg: Config, profiles: dict, guardrails: dict | None = None) -> tuple[dict, list[dict]]:
    guardrails = guardrails or {}
    model_list, fallbacks, teams = [], [], []
    for t in cfg.tenants.values():
        team_models, aliases = [], {}
        for alias in t.aliases:
            try:
                chain = cfg.resolve(alias, t)
            except NotEntitled:
                continue
            names = []
            for i, target in enumerate(chain):
                if target.provider != "bedrock":
                    continue
                name = group(alias, t.tenant, i)
                params = {
                    "model": f"bedrock/converse/{target.model}",
                    "aws_region_name": target.region,
                    "model_id": profiles.get(f"{t.tenant}|{target.model}|{target.region}",
                                             f"MISSING_PROFILE:{t.tenant}|{target.model}|{target.region}"),
                }
                g = guardrails.get(str(t.risk_tier))
                if g:
                    params["guardrailConfig"] = {"guardrailIdentifier": g["guardrailIdentifier"],
                                                 "guardrailVersion": str(g["guardrailVersion"])}
                model_list.append({
                    "model_name": name,
                    "litellm_params": params,
                    "model_info": {"platform_alias": alias, "tenant": t.tenant, "platform_tier": target.tier,
                                   "cache": target.cache, "fallback": target.is_fallback},
                })
                names.append(name)
            if names:
                aliases[alias] = names[0]
                team_models.extend(names)
                if len(names) > 1:
                    fallbacks.append({names[0]: names[1:]})
        teams.append({
            "team_alias": t.tenant,
            "models": team_models,
            "model_aliases": aliases,
            "tpm_limit": t.tokens_per_minute or None,
            "max_budget": t.monthly_budget_usd,
            "budget_duration": "30d",
            "metadata": {"class": t.klass, "risk_tier": t.risk_tier, "source": "gateway/tenants"},
        })
    config = {
        "model_list": model_list,
        "router_settings": {"fallbacks": fallbacks, "num_retries": 1, "timeout": 120,
                            "routing_strategy": "simple-shuffle"},
        "litellm_settings": {"cache": True,
                             "cache_params": {"type": "redis", "mode": "default_off",
                                              "host": "os.environ/REDIS_HOST",
                                              "port": "os.environ/REDIS_PORT"},
                             "callbacks": ["otel"], "drop_params": False},
        # The Helm chart provides PROXY_MASTER_KEY and builds DATABASE_URL (IAM auth).
        "general_settings": {"master_key": "os.environ/PROXY_MASTER_KEY"},
    }
    return config, teams


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default="prod")
    ap.add_argument("--profiles", help="JSON map tenant|model|region → profile ARN (terraform output)")
    ap.add_argument("--guardrails", help="JSON map risk tier → guardrail id/version")
    ap.add_argument("--out", default="build")
    a = ap.parse_args()
    cfg = Config.load(GATEWAY_DIR, environment=a.env)
    profiles = json.loads(pathlib.Path(a.profiles).read_text()) if a.profiles else {}
    guardrails = json.loads(pathlib.Path(a.guardrails).read_text()) if a.guardrails else {}
    config, teams = render(cfg, profiles, guardrails)
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "litellm-config.yaml").write_text(yaml.safe_dump(config, sort_keys=False))
    (out / "litellm-teams.json").write_text(json.dumps(teams, indent=2))
    missing = [m["model_name"] for m in config["model_list"]
               if m["litellm_params"]["model_id"].startswith("MISSING_PROFILE")]
    print(f"rendered {len(config['model_list'])} deployments, {len(teams)} teams → {out}")
    if missing:
        print(f"WARNING: {len(missing)} deployments have no application profile: {missing[:5]}")


if __name__ == "__main__":
    main()
