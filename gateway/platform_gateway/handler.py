"""The reference custom gateway (Section 4.6, Figure 4.7), behind the platform API
contract (Section 4.7, Figure 4.8).

It is deliberately small so its gaps stay visible. Compared with the book's trimmed
figure it adds the two things the local labs need — the fallback chain and an exact,
per-tenant cache — and still lacks streaming, retry budgets across instances, semantic
caching and config distribution. Production estates run the proxy of Section 4.5 behind
the same contract; tests/conformance proves either one serves it.
"""
from __future__ import annotations

import hashlib
import json
import re
import secrets
import threading
import time

from .admission import Admission, QuotaExceeded
from .backends import UpstreamError
from .config import Config, NotEntitled
from .metering import MemorySink, make_event

TRACEPARENT = re.compile(r"^00-([0-9a-f]{32})-([0-9a-f]{16})-[0-9a-f]{2}$")


class Unauthorized(Exception):
    pass


class Forbidden(Exception):
    pass


def normalize_role_arn(arn: str) -> str:
    """arn:aws:sts::123:assumed-role/NAME/session → arn:aws:iam::123:role/NAME."""
    m = re.match(r"^arn:(aws[\w-]*):sts::(\d{12}):assumed-role/([^/]+)/.+$", arn or "")
    return f"arn:{m.group(1)}:iam::{m.group(2)}:role/{m.group(3)}" if m else arn


class ExactCache:
    """Exact-match response cache, keyed per tenant so a cache can never leak (5.4)."""

    def __init__(self, ttl_s: int = 3600):
        self.ttl = ttl_s
        self.store: dict[str, tuple[float, dict]] = {}
        self.lock = threading.Lock()

    @staticmethod
    def key(tenant: str, alias: str, env: str, body: dict) -> str:
        material = json.dumps([tenant, alias, env, body.get("messages"), body.get("max_tokens"),
                               body.get("temperature")], sort_keys=True)
        return hashlib.sha256(material.encode()).hexdigest()

    def get(self, k: str):
        with self.lock:
            hit = self.store.get(k)
            if hit and time.time() - hit[0] < self.ttl:
                return hit[1]
            self.store.pop(k, None)
            return None

    def put(self, k: str, value: dict) -> None:
        with self.lock:
            self.store[k] = (time.time(), value)


class Gateway:
    def __init__(self, config: Config, backend, sink=None, admission: Admission | None = None,
                 cache: ExactCache | None = None):
        self.config = config
        self.backend = backend
        self.sink = sink or MemorySink()
        self.admission = admission or Admission(config.tenants)
        self.cache = cache or ExactCache(config.settings.get("cache_ttl_s", 3600))
        self.max_attempts = int(config.settings.get("max_attempts", 3))

    # -- responsibility 1: identity ----------------------------------------------------
    def authenticate(self, identity: dict):
        if not identity:
            raise Unauthorized("no workload identity on the request")
        kind, value = identity.get("kind"), identity.get("value")
        for t in self.config.tenants.values():
            ids = t.identities
            if kind == "iam" and normalize_role_arn(value) in (
                    ids.get("workload_role"), ids.get("pod_identity_role")):
                return t
            if kind == "api_key" and value and value == ids.get("local_api_key"):
                return t
        raise Unauthorized("identity is not bound to any tenant record")

    # -- the request path ----------------------------------------------------------------
    def chat(self, identity: dict, headers: dict, body: dict) -> tuple[int, dict, dict]:
        h = {k.lower(): v for k, v in (headers or {}).items()}
        trace_id = self._trace_id(h.get("traceparent"))
        feature = h.get("x-platform-feature", "unspecified")
        convo_id = h.get("x-platform-conversation")
        out_headers = {"x-platform-trace-id": trace_id}
        try:
            tenant = self.authenticate(identity)
            claimed = h.get("x-platform-tenant")
            if claimed and claimed != tenant.tenant:
                raise Forbidden(f"x-platform-tenant {claimed!r} does not match the verified identity")
            alias = body.get("model")
            messages = body.get("messages")
            if not alias or not isinstance(messages, list) or not messages:
                return self._error(400, "invalid_request", "model and messages are required", trace_id, out_headers)
            max_tokens = int(body.get("max_tokens") or 1024)
            chain = self.config.resolve(alias, tenant)
            data_class = h.get("x-platform-data-class")
            if data_class and not self.config.data_class_allowed(alias, data_class):
                return self._error(403, "matrix_blocked",
                                   f"data class {data_class!r} is not allowed on alias {alias!r} (Section 10.3)",
                                   trace_id, out_headers)
        except Unauthorized as e:
            return self._error(401, "unauthenticated", str(e), trace_id, out_headers)
        except (Forbidden, NotEntitled) as e:
            return self._error(403, "not_entitled", str(e), trace_id, out_headers)

        base = dict(trace_id=trace_id, tenant=tenant.tenant, feature=feature, convo_id=convo_id,
                    alias=alias, environment=self.config.environment,
                    config_version=self.config.version)

        # responsibility 5: exact cache, where the alias contract allows it
        ck = None
        if chain[0].cache == "exact":
            ck = self.cache.key(tenant.tenant, alias, self.config.environment, body)
            cached = self.cache.get(ck)
            if cached is not None:
                self.sink.emit(make_event(**base, provider=chain[0].provider, model=chain[0].model,
                                          region=chain[0].region, status=200, cache_hit=True,
                                          fallback=False, attempts=0, tokens_in=0, tokens_out=0,
                                          tokens_cached=0, cost_usd=0.0, latency_ms=0))
                return 200, dict(out_headers, **{"x-platform-cache": "hit"}), cached

        # responsibility 3: admission with a worst-case debit
        try:
            reservation = self.admission.admit(tenant, max_tokens, messages, trace_id)
        except QuotaExceeded as q:
            r = q.rejection
            self.sink.emit(make_event(**base, status=429, cache_hit=False, attempts=0, cost_usd=0.0))
            return r.status, dict(out_headers, **r.headers), r.body

        # responsibility 4: the fallback chain
        attempts, last_error, degraded = 0, None, None
        t0 = time.perf_counter()
        for target in self._chain_with_degradation(chain, tenant):
            # The attempt budget bounds the alias's own chain; a degradation step gets one try.
            if attempts >= self.max_attempts and target.alias == alias:
                continue
            if attempts >= self.max_attempts + 1:
                break
            attempts += 1
            try:
                result = self.backend.call(tenant, target, messages, max_tokens, body.get("temperature"))
            except UpstreamError as e:
                last_error = e
                if not e.retryable:
                    break
                continue
            if target.alias != alias:
                degraded = "cheaper_alias"
            actual = self.admission.settle(reservation, result.input_tokens, result.output_tokens)
            cost = self.config.cost_usd(target, result.input_tokens, result.output_tokens,
                                        result.cached_input_tokens)
            latency = round((time.perf_counter() - t0) * 1000, 1)
            self.sink.emit(make_event(**base, provider=target.provider, model=result.model or target.model,
                                      region=target.region, tier=target.tier, status=200,
                                      fallback=target.is_fallback or degraded is not None,
                                      attempts=attempts, cache_hit=False,
                                      tokens_in=result.input_tokens, tokens_out=result.output_tokens,
                                      tokens_cached=result.cached_input_tokens, cost_usd=cost,
                                      latency_ms=latency, faults=result.guardrail.get("faults")))
            resp = self.to_platform_contract(alias, result, trace_id, actual)
            hdrs = dict(out_headers, **{"x-platform-served-by": f"{target.provider}/{result.model or target.model}",
                                        "x-platform-region": target.region,
                                        "x-platform-fallback": str(target.is_fallback).lower()})
            if degraded:
                hdrs["x-platform-degraded"] = degraded
            if ck:
                self.cache.put(ck, resp)
                hdrs["x-platform-cache"] = "miss"
            return 200, hdrs, resp

        self.admission.settle(reservation, 0, 0)
        self.sink.emit(make_event(**base, status=503, attempts=attempts, cache_hit=False, cost_usd=0.0,
                                  fallback=attempts > 1))
        code = last_error.code if last_error else "no_target"
        status = 503 if (last_error is None or last_error.retryable) else 502
        return self._error(status, "upstream_unavailable", f"all targets failed ({code})", trace_id, out_headers)

    def _chain_with_degradation(self, chain, tenant):
        yield from chain
        # Degradation ladder (9.3): opted-in tenants step down to a cheaper alias.
        if "cheaper_alias" in tenant.degradation and chain[0].alias != "fast" and "fast" in tenant.aliases:
            try:
                yield from self.config.resolve("fast", tenant)
            except NotEntitled:
                return

    @staticmethod
    def to_platform_contract(alias: str, result, trace_id: str, total_tokens: int) -> dict:
        return {
            "id": f"chatcmpl-{trace_id[:24]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": alias,                      # the alias, never a provider ID
            "choices": [{"index": 0,
                         "message": {"role": "assistant", "content": result.text},
                         "finish_reason": "stop" if result.stop_reason in ("end_turn", "stop_sequence")
                         else ("length" if result.stop_reason == "max_tokens" else result.stop_reason)}],
            "usage": {"prompt_tokens": result.input_tokens,
                      "completion_tokens": result.output_tokens,
                      "total_tokens": total_tokens},
            "platform": {"trace_id": trace_id},
        }

    @staticmethod
    def _trace_id(traceparent: str | None) -> str:
        m = TRACEPARENT.match(traceparent or "")
        return m.group(1) if m else secrets.token_hex(16)

    @staticmethod
    def _error(status, code, message, trace_id, headers):
        return status, headers, {"error": code, "message": message, "trace_id": trace_id}
