"""Alias map, tenant records and price table: loading and resolution (Sections 4.3, 5.2).

The gateway reads three kinds of configuration, all from Git:
  aliases.yaml      — capability names resolving per environment (Figure 4.3)
  tenants/*.yaml    — one reviewable record per tenant (Figure 5.3)
  prices.yaml       — the price table the metering uses (Section 4.2, responsibility 8)
"""
from __future__ import annotations

import os
import pathlib
import re
from dataclasses import dataclass, field

import yaml

GATEWAY_DIR = pathlib.Path(__file__).resolve().parents[1]
SAME_MODEL_CROSS_REGION = "same-model-cross-region"


class ConfigError(ValueError):
    pass


class NotEntitled(PermissionError):
    """The tenant may not use this alias (entitlement or approval missing)."""


@dataclass(frozen=True)
class Target:
    """One concrete way to serve an alias: a model in a region, with its policies."""
    alias: str
    model: str            # provider model ID without the "bedrock/" prefix
    provider: str         # "bedrock" | "mock"
    region: str
    tier: str | None = None
    cache: str | None = None
    is_fallback: bool = False

    @property
    def label(self) -> str:
        return f"{self.provider}/{self.model}@{self.region}"


@dataclass
class Tenant:
    tenant: str
    raw: dict
    aliases: list[str] = field(default_factory=list)
    klass: str = "standard"
    risk_tier: int = 1
    tokens_per_minute: int = 0
    monthly_budget_usd: float | None = None
    degradation: list[str] = field(default_factory=list)
    fail_policy: str = "open-with-ceiling"

    @classmethod
    def from_record(cls, rec: dict) -> "Tenant":
        if "tenant" not in rec:
            raise ConfigError("tenant record without 'tenant'")
        q = rec.get("quota", {}) or {}
        return cls(
            tenant=rec["tenant"], raw=rec,
            aliases=list(rec.get("aliases", [])),
            klass=rec.get("class", "standard"),
            risk_tier=int(rec.get("risk_tier", 1)),
            tokens_per_minute=int(q.get("tokens_per_minute", 0)),
            monthly_budget_usd=q.get("monthly_budget_usd"),
            degradation=list(rec.get("degradation", [])),
            fail_policy=rec.get("fail_policy", "open-with-ceiling"),
        )

    @property
    def identities(self) -> dict:
        """Identity bindings, with ${PLATFORM_ACCOUNT_ID} expanded so lab records are portable."""
        ids = self.raw.get("identity", {}) or {}
        return {k: os.path.expandvars(v) if isinstance(v, str) else v for k, v in ids.items()}


def _split_model(spec: str) -> tuple[str, str]:
    if "/" not in spec:
        raise ConfigError(f"model spec must be provider/model: {spec!r}")
    provider, model = spec.split("/", 1)
    if provider not in ("bedrock", "mock"):
        raise ConfigError(f"unknown provider {provider!r} in {spec!r}")
    return provider, model


def _approval_ok(rule: str | None, tenant: Tenant) -> bool:
    if not rule:
        return True
    m = re.fullmatch(r"use-case-tier>=(\d)", rule.strip())
    if not m:
        raise ConfigError(f"unsupported approval rule {rule!r}")
    return tenant.risk_tier >= int(m.group(1))


class Config:
    def __init__(self, aliases: dict, tenants: dict[str, Tenant], prices: dict,
                 environment: str, regions: dict, settings: dict | None = None):
        self.aliases = aliases
        self.tenants = tenants
        self.prices = prices
        self.environment = environment
        self.regions = regions
        self.settings = settings or {}
        self.version = self.settings.get("config_version", "local")
        self._validate()

    # -- loading -----------------------------------------------------------------
    @classmethod
    def load(cls, base: pathlib.Path | str = GATEWAY_DIR, environment: str | None = None,
             overlay: pathlib.Path | str | None = None) -> "Config":
        base = pathlib.Path(base)
        settings = yaml.safe_load((base / "settings.yaml").read_text())
        env = environment or os.environ.get("PLATFORM_ENV") or settings.get("environment", "prod")
        aliases = yaml.safe_load((base / "aliases.yaml").read_text())
        overlay = overlay or (base / "env" / f"{env}.yaml")
        if pathlib.Path(overlay).exists():
            for alias, spec in (yaml.safe_load(pathlib.Path(overlay).read_text()) or {}).items():
                aliases.setdefault(alias, {}).update(spec)
        tenants = {}
        for p in sorted((base / "tenants").glob("*.yaml")):
            t = Tenant.from_record(yaml.safe_load(p.read_text()))
            tenants[t.tenant] = t
        prices = yaml.safe_load((base / "prices.yaml").read_text())
        contracts = {p.stem: yaml.safe_load(p.read_text()) for p in sorted((base / "contracts").glob("*.yaml"))}
        settings = dict(settings, contracts=contracts)
        regions = settings.get("regions", {"primary": "us-east-1", "secondary": "us-west-2"})
        return cls(aliases, tenants, prices, env, regions, settings)

    def _validate(self) -> None:
        for alias, spec in self.aliases.items():
            if "prod" not in spec and self.environment not in spec:
                raise ConfigError(f"alias {alias!r} has no prod entry")
            for env, entry in spec.items():
                if env == "fallback":
                    for fb in entry:
                        if fb != SAME_MODEL_CROSS_REGION:
                            _split_model(fb)
                    continue
                _split_model(entry["model"])
        # Metering refuses to guess (4.2): a model without a price never reaches traffic.
        for alias, spec in self.aliases.items():
            for env, entry in spec.items():
                models = entry if env == "fallback" else [entry["model"]]
                for m in models:
                    if m == SAME_MODEL_CROSS_REGION:
                        continue
                    provider, model = _split_model(m)
                    key = model if provider == "bedrock" else f"mock/{model}"
                    if key not in self.prices.get("models", {}):
                        raise ConfigError(f"alias {alias!r} ({env}) resolves to {m!r}, which has no price")
        for t in self.tenants.values():
            unknown = set(t.aliases) - set(self.aliases)
            if unknown:
                raise ConfigError(f"tenant {t.tenant!r} entitled to unknown aliases {sorted(unknown)}")

    # -- resolution ----------------------------------------------------------------
    def data_class_allowed(self, alias: str, data_class: str) -> bool:
        """The data-class matrix (Section 10.3): the alias contract lists what it may carry."""
        c = self.settings.get("contracts", {}).get(alias)
        return c is None or data_class in c.get("data_classes_allowed", [])

    def entry(self, alias: str) -> dict:
        if alias not in self.aliases:
            raise NotEntitled(f"unknown alias {alias!r}")
        spec = self.aliases[alias]
        return spec.get(self.environment) or spec["prod"]

    def resolve(self, alias: str, tenant: Tenant) -> list[Target]:
        """Return the ordered chain of targets for (alias, tenant, environment).

        The first element is the primary target; the rest are the fallback chain.
        Entitlement and approval are checked here, so nothing downstream can skip them.
        """
        if alias not in tenant.aliases:
            raise NotEntitled(f"tenant {tenant.tenant!r} is not entitled to alias {alias!r}")
        entry = self.entry(alias)
        if not _approval_ok(entry.get("approval"), tenant):
            raise NotEntitled(f"alias {alias!r} requires {entry['approval']} "
                              f"(tenant {tenant.tenant!r} is tier {tenant.risk_tier})")
        provider, model = _split_model(entry["model"])
        primary = Target(alias, model, provider, self.regions["primary"],
                         tier=entry.get("tier"), cache=entry.get("cache"))
        chain = [primary]
        for fb in self.aliases[alias].get("fallback", []):
            if fb == SAME_MODEL_CROSS_REGION:
                chain.append(Target(alias, model, provider, self.regions["secondary"],
                                    tier=entry.get("tier"), is_fallback=True))
            else:
                p, m = _split_model(fb)
                chain.append(Target(alias, m, p, self.regions["primary"], is_fallback=True))
        return chain

    # -- pricing -------------------------------------------------------------------
    def cost_usd(self, target: Target, tokens_in: int, tokens_out: int, cached_in: int = 0) -> float:
        key = target.model if target.provider == "bedrock" else f"mock/{target.model}"
        p = self.prices["models"].get(key)
        if p is None:
            raise ConfigError(f"no price for {key!r}: metering refuses to guess (4.2)")
        mult = self.prices.get("tiers", {}).get(target.tier or "default", 1.0)
        fresh_in = max(tokens_in - cached_in, 0)
        cost = (fresh_in * p["input"] + cached_in * p.get("cached_read", p["input"])
                + tokens_out * p["output"]) / 1_000_000
        return round(cost * mult, 8)
