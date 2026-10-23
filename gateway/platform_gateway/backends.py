"""Model backends: Amazon Bedrock (Converse API) and a deterministic mock for local labs.

Both return the same ModelResult, so everything above this layer — admission, fallback,
metering, the platform contract — is identical in local mode and on AWS.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field

from .config import Target


class UpstreamError(Exception):
    """A model call failed. retryable=True means the fallback chain may continue."""

    def __init__(self, message: str, retryable: bool = True, code: str = "upstream_error"):
        super().__init__(message)
        self.retryable = retryable
        self.code = code


@dataclass
class ModelResult:
    text: str
    input_tokens: int
    output_tokens: int
    cached_input_tokens: int = 0
    stop_reason: str = "end_turn"
    model: str = ""
    region: str = ""
    latency_ms: float = 0.0
    guardrail: dict = field(default_factory=dict)


def to_converse(messages: list[dict]) -> tuple[list[dict], list[dict]]:
    """OpenAI-style messages → (Converse messages, Converse system blocks)."""
    system, out = [], []
    for m in messages:
        content = m.get("content", "")
        text = content if isinstance(content, str) else " ".join(
            p.get("text", "") for p in content if isinstance(p, dict))
        if m.get("role") == "system":
            system.append({"text": text})
        else:
            out.append({"role": m.get("role", "user"), "content": [{"text": text}]})
    return out, system


RETRYABLE_CODES = {"ThrottlingException", "ServiceUnavailableException", "ModelNotReadyException",
                   "InternalServerException", "ModelTimeoutException"}


class BedrockBackend:
    """Calls Bedrock through the tenant's application inference profile (Section 4.4).

    profile_map: {"<tenant>|<model>|<region>": "<application-inference-profile ARN>"},
    produced by gateway/terraform (one profile per tenant, model and region).
    guardrails:  {"<risk tier>": {"guardrailIdentifier": ..., "guardrailVersion": ...}}
    """

    def __init__(self, profile_map: dict | None = None, guardrails: dict | None = None,
                 client_factory=None):
        self.profile_map = profile_map if profile_map is not None else json.loads(
            os.environ.get("PLATFORM_PROFILE_MAP", "{}"))
        self.guardrails = guardrails if guardrails is not None else json.loads(
            os.environ.get("PLATFORM_GUARDRAILS", "{}"))
        if client_factory is None:
            import boto3
            from botocore.config import Config as BotoConfig
            cfg = BotoConfig(retries={"max_attempts": 1, "mode": "standard"}, read_timeout=120)
            client_factory = lambda region: boto3.client("bedrock-runtime", region_name=region, config=cfg)
        self._factory = client_factory
        self._clients: dict = {}

    def client(self, region: str):
        if region not in self._clients:
            self._clients[region] = self._factory(region)
        return self._clients[region]

    def profile_for(self, tenant: str, target: Target) -> str:
        key = f"{tenant}|{target.model}|{target.region}"
        try:
            return self.profile_map[key]
        except KeyError:
            raise UpstreamError(f"no application inference profile for {key}; the org SCP "
                                f"denies calls without one (Figure 3.1)", retryable=True,
                                code="no_application_profile") from None

    def converse_params(self, tenant, target: Target, messages: list[dict], max_tokens: int,
                        temperature: float | None) -> dict:
        conv, system = to_converse(messages)
        params = {
            "modelId": self.profile_for(tenant.tenant, target),
            "messages": conv,
            "inferenceConfig": {"maxTokens": max_tokens},
        }
        if temperature is not None:
            params["inferenceConfig"]["temperature"] = temperature
        if system:
            params["system"] = system
        g = self.guardrails.get(str(tenant.risk_tier))
        if g:
            params["guardrailConfig"] = {"guardrailIdentifier": g["guardrailIdentifier"],
                                         "guardrailVersion": str(g["guardrailVersion"])}
        if target.tier and target.tier != "default":
            params["serviceTier"] = {"type": target.tier}
        return params

    def call(self, tenant, target: Target, messages: list[dict], max_tokens: int,
             temperature: float | None = None) -> ModelResult:
        from botocore.exceptions import ClientError, EndpointConnectionError, ReadTimeoutError
        params = self.converse_params(tenant, target, messages, max_tokens, temperature)
        t0 = time.perf_counter()
        try:
            resp = self.client(target.region).converse(**params)
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "ClientError")
            raise UpstreamError(f"{code}: {e}", retryable=code in RETRYABLE_CODES, code=code) from e
        except (EndpointConnectionError, ReadTimeoutError) as e:
            raise UpstreamError(str(e), retryable=True, code="connection") from e
        usage = resp.get("usage", {})
        content = resp.get("output", {}).get("message", {}).get("content", [])
        text = "".join(c.get("text", "") for c in content)
        return ModelResult(
            text=text,
            input_tokens=usage.get("inputTokens", 0),
            output_tokens=usage.get("outputTokens", 0),
            cached_input_tokens=usage.get("cacheReadInputTokens", 0),
            stop_reason=resp.get("stopReason", ""),
            model=target.model, region=target.region,
            latency_ms=(time.perf_counter() - t0) * 1000,
            guardrail={"action": resp.get("stopReason") == "guardrail_intervened" and "intervened" or "none"},
        )


class MockBackend:
    """Deterministic stand-in for Bedrock. Same inputs → same outputs, so proofs are stable.

    Each mock model has a per-call latency and a 'quality' label that the evaluation
    labs (Chapter 8) can detect. Outages and degradations come from the fault layer.
    """

    MODELS = {
        "model-a": {"latency_ms": 40, "quality": "strong"},
        "model-b": {"latency_ms": 30, "quality": "strong"},
        "model-c": {"latency_ms": 35, "quality": "adequate"},
        "model-f": {"latency_ms": 10, "quality": "adequate"},
        "model-p": {"latency_ms": 80, "quality": "strongest"},
        "model-weak": {"latency_ms": 25, "quality": "weak"},
    }

    def __init__(self, sleep: bool = True):
        self.sleep = sleep
        self.calls = 0

    def call(self, tenant, target: Target, messages: list[dict], max_tokens: int,
             temperature: float | None = None) -> ModelResult:
        spec = self.MODELS.get(target.model)
        if spec is None:
            raise UpstreamError(f"mock model {target.model!r} does not exist", retryable=False,
                                code="ValidationException")
        self.calls += 1
        from .admission import count_input
        prompt = " ".join(str(m.get("content", "")) for m in messages if m.get("role") != "system")
        digest = hashlib.sha256(f"{target.model}|{prompt}".encode()).hexdigest()[:8]
        words = 12 if spec["quality"] != "weak" else 5
        if spec["quality"] != "weak" and any(w in prompt.lower() for w in ("sue ", "lawsuit", "legal advice")):
            # Instruction-following, simulated: non-weak models decline legal advice.
            text = f"[{target.model}:{spec['quality']}] I can't give legal advice; the support team can help."
        else:
            text = (f"[{target.model}:{spec['quality']}] answer {digest} to: {prompt[:60]}"
                    + " detail" * words)
        out_tokens = min(max_tokens, 20 + words)
        if self.sleep:
            time.sleep(spec["latency_ms"] / 1000)
        return ModelResult(text=text, input_tokens=count_input(messages) - 4 * len(messages) + 3,
                           output_tokens=out_tokens, model=target.model, region=target.region,
                           latency_ms=spec["latency_ms"])
