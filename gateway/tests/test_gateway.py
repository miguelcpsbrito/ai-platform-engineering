"""Unit tests for the gateway: resolution, admission, fallback, cache, metering, contract."""
import json
import pathlib
import sys

import pytest

GW = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GW))

from platform_gateway.admission import Admission, TokenBucket, count_input  # noqa: E402
from platform_gateway.backends import BedrockBackend, MockBackend, UpstreamError  # noqa: E402
from platform_gateway.config import Config, ConfigError, NotEntitled  # noqa: E402
from platform_gateway.faults import FaultLayer  # noqa: E402
from platform_gateway.handler import Gateway, normalize_role_arn  # noqa: E402
from platform_gateway.metering import EVENT_FIELDS, MemorySink  # noqa: E402

KEY_A = {"kind": "api_key", "value": "lab-key-tenant-a"}
KEY_B = {"kind": "api_key", "value": "lab-key-tenant-b"}
MSG = [{"role": "user", "content": "What does the extended plan cover?"}]


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


@pytest.fixture
def cfg():
    return Config.load(GW, environment="local")


@pytest.fixture
def gw(cfg):
    return Gateway(cfg, FaultLayer(MockBackend(sleep=False)), sink=MemorySink())


# --- Figure 4.3: the alias map -------------------------------------------------------

def test_book_alias_map_resolves_in_prod():
    cfg = Config.load(GW, environment="prod")
    t = cfg.tenants["tenant-b"]
    chain = cfg.resolve("standard", t)
    assert chain[0].model == "us.anthropic.claude-sonnet-4-6" and chain[0].tier == "priority"
    assert chain[1].model == chain[0].model and chain[1].region == "us-west-2"   # same model, other region
    assert chain[2].model == "us.amazon.nova-pro-v1:0"
    assert cfg.resolve("fast", t)[0].cache == "exact"


def test_staging_resolves_to_a_cheaper_model():
    cfg = Config.load(GW, environment="staging")
    assert cfg.resolve("standard", cfg.tenants["tenant-a"])[0].model == "us.amazon.nova-lite-v1:0"
    # no staging entry → prod entry (Section 4.3)
    assert cfg.resolve("fast", cfg.tenants["tenant-a"])[0].model == "us.amazon.nova-micro-v1:0"


def test_premium_requires_tier_two(cfg):
    with pytest.raises(NotEntitled):
        cfg.resolve("premium", cfg.tenants["tenant-a"])      # not entitled at all
    cfg.tenants["tenant-a"].aliases.append("premium")
    with pytest.raises(NotEntitled, match="use-case-tier>=2"):
        cfg.resolve("premium", cfg.tenants["tenant-a"])      # entitled, but tier 1
    assert cfg.resolve("premium", cfg.tenants["tenant-b"])[0].model == "model-p"


def test_every_priced_model(cfg):
    prod = Config.load(GW, environment="prod")
    for alias in prod.aliases:
        for target in prod.resolve(alias, prod.tenants["tenant-b"]):
            assert prod.cost_usd(target, 1000, 100) > 0


def test_unknown_alias_entitlement_is_a_config_error(cfg):
    from platform_gateway.config import Tenant
    bad = dict(cfg.tenants)
    bad["x"] = Tenant.from_record({"tenant": "x", "aliases": ["turbo"]})
    with pytest.raises(ConfigError):
        Config(cfg.aliases, bad, cfg.prices, "local", cfg.regions)


# --- Figure 5.4: two-phase accounting ------------------------------------------------

def test_bucket_debit_credit_and_eta():
    clock = Clock()
    b = TokenBucket(6000, clock=clock)              # 100 tokens/s
    assert b.try_debit(6000)
    assert not b.try_debit(100)
    assert b.eta(100) == 1
    b.credit(500)                                   # settlement gives back unused
    assert b.try_debit(500)
    clock.t += 30                                   # 3000 tokens refill
    assert b.try_debit(3000) and not b.try_debit(1)


def test_burst_is_capped_at_twice_the_rate():
    clock = Clock()
    b = TokenBucket(6000, clock=clock)
    clock.t += 3600
    assert b.try_debit(12000) and not b.try_debit(1)


def test_settle_bills_actual_tokens(cfg):
    adm = Admission(cfg.tenants, clock=Clock())
    t = cfg.tenants["tenant-a"]
    res = adm.admit(t, 1000, MSG, "t" * 32)
    assert res.est == count_input(MSG) + 1000
    assert adm.settle(res, 30, 40) == 70


# --- Figure 5.5: the 429 contract ------------------------------------------------------

def test_quota_rejection_is_machine_readable(gw):
    big = [{"role": "user", "content": "x" * 70000}]   # ~17.5k tokens + 4096 > 20k tpm
    status, headers, body = gw.chat(KEY_A, {}, {"model": "standard", "messages": big, "max_tokens": 4096})
    assert status == 429 and int(headers["Retry-After"]) >= 1
    for k in ("error", "limit", "window_s", "limit_value", "current", "class", "raise_request", "trace_id"):
        assert k in body
    assert body["error"] == "tenant_quota_exceeded" and body["limit_value"] == 20000


# --- identity and the contract -------------------------------------------------------------

def test_missing_identity_is_401_and_spoofed_tenant_is_403(gw):
    assert gw.chat({}, {}, {"model": "standard", "messages": MSG})[0] == 401
    status, _, body = gw.chat(KEY_A, {"x-platform-tenant": "tenant-b"}, {"model": "standard", "messages": MSG})
    assert status == 403


def test_assumed_role_arn_normalizes():
    assert normalize_role_arn("arn:aws:sts::111122223333:assumed-role/lab-tenant-a/i-0abc") == \
        "arn:aws:iam::111122223333:role/lab-tenant-a"


def test_response_names_the_alias_never_the_model(gw):
    status, headers, body = gw.chat(KEY_A, {"x-platform-feature": "refund-flow"},
                                    {"model": "standard", "messages": MSG})
    assert status == 200 and body["model"] == "standard"
    envelope = {k: v for k, v in body.items() if k != "choices"}   # the mock echoes its name in text
    assert "model-a" not in json.dumps(envelope)
    assert headers["x-platform-served-by"] == "mock/model-a"


def test_traceparent_is_propagated(gw):
    tp = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    _, headers, body = gw.chat(KEY_A, {"traceparent": tp}, {"model": "standard", "messages": MSG})
    assert body["platform"]["trace_id"] == "4bf92f3577b34da6a3ce929d0e0e4736"


# --- responsibility 4: fallback ------------------------------------------------------------

def test_primary_region_failure_falls_back_to_same_model(gw):
    gw.backend.load([{"match": "model-a@us-east-1", "error_rate": 1.0}])
    status, headers, _ = gw.chat(KEY_A, {}, {"model": "standard", "messages": MSG})
    assert status == 200 and headers["x-platform-region"] == "us-west-2"
    assert headers["x-platform-fallback"] == "true"
    assert gw.sink.events[-1]["fallback"] is True and gw.sink.events[-1]["attempts"] == 2


def test_all_targets_down_degrades_to_cheaper_alias(gw):
    gw.backend.load([{"match": "model-a@*", "error_rate": 1.0}, {"match": "model-c@*", "error_rate": 1.0}])
    status, headers, _ = gw.chat(KEY_A, {}, {"model": "standard", "messages": MSG})
    assert status == 200 and headers["x-platform-degraded"] == "cheaper_alias"


def test_everything_down_is_503_and_metered(gw):
    gw.backend.load([{"match": "*", "error_rate": 1.0}])
    status, _, body = gw.chat(KEY_B, {}, {"model": "standard", "messages": MSG})
    assert status == 503 and body["error"] == "upstream_unavailable"
    assert gw.sink.events[-1]["status"] == 503


# --- responsibility 5: exact cache, per tenant -------------------------------------------------

def test_fast_alias_caches_per_tenant(gw):
    body = {"model": "fast", "messages": MSG}
    assert gw.chat(KEY_A, {}, body)[1]["x-platform-cache"] == "miss"
    assert gw.chat(KEY_A, {}, body)[1]["x-platform-cache"] == "hit"
    assert gw.chat(KEY_B, {}, body)[1]["x-platform-cache"] == "miss"   # never shared across tenants


# --- responsibility 8: metering ----------------------------------------------------------------

def test_metering_event_schema_and_cost(gw):
    gw.chat(KEY_A, {"x-platform-feature": "refund-flow", "x-platform-conversation": "c-1"},
            {"model": "standard", "messages": MSG})
    ev = gw.sink.events[-1]
    assert set(ev) == set(EVENT_FIELDS)
    assert ev["tenant"] == "tenant-a" and ev["feature"] == "refund-flow" and ev["convo_id"] == "c-1"
    expected = (ev["tokens_in"] * 3.00 + ev["tokens_out"] * 15.00) / 1e6
    assert ev["cost_usd"] == pytest.approx(expected)
    assert "content" not in ev and "messages" not in ev


# --- the Bedrock backend, validated against the real botocore service model ----------------------

def test_converse_request_is_valid_for_bedrock_runtime():
    import boto3
    from botocore.stub import Stubber
    cfg = Config.load(GW, environment="prod")
    client = boto3.client("bedrock-runtime", region_name="us-east-1",
                          aws_access_key_id="x", aws_secret_access_key="x")
    stub = Stubber(client)
    arn = "arn:aws:bedrock:us-east-1:111122223333:application-inference-profile/abc123"
    t = cfg.tenants["tenant-b"]
    target = cfg.resolve("standard", t)[0]
    backend = BedrockBackend(profile_map={f"tenant-b|{target.model}|us-east-1": arn},
                             guardrails={"2": {"guardrailIdentifier": "gr-123", "guardrailVersion": 3}},
                             client_factory=lambda region: client)
    params = backend.converse_params(t, target, [{"role": "system", "content": "be brief"}] + MSG, 800, 0.2)
    assert params["serviceTier"] == {"type": "priority"}
    assert params["guardrailConfig"] == {"guardrailIdentifier": "gr-123", "guardrailVersion": "3"}
    stub.add_response("converse", {
        "output": {"message": {"role": "assistant", "content": [{"text": "covered"}]}},
        "stopReason": "end_turn",
        "usage": {"inputTokens": 12, "outputTokens": 3, "totalTokens": 15},
        "metrics": {"latencyMs": 100}}, params)          # Stubber validates params against the model
    with stub:
        r = backend.call(t, target, [{"role": "system", "content": "be brief"}] + MSG, 800, 0.2)
    assert r.text == "covered" and r.input_tokens == 12


def test_missing_application_profile_fails_before_the_scp_would():
    cfg = Config.load(GW, environment="prod")
    t = cfg.tenants["tenant-b"]
    backend = BedrockBackend(profile_map={}, guardrails={}, client_factory=lambda r: None)
    with pytest.raises(UpstreamError, match="application inference profile"):
        backend.call(t, cfg.resolve("standard", t)[0], MSG, 100)


def test_lambda_adapter_uses_iam_identity(monkeypatch):
    from platform_gateway import lambda_handler
    monkeypatch.setenv("PLATFORM_ACCOUNT_ID", "111122223333")
    cfg = Config.load(GW, environment="local")
    lambda_handler._GW = Gateway(cfg, FaultLayer(MockBackend(sleep=False)), sink=MemorySink())
    event = {"rawPath": "/v1/chat/completions",
             "requestContext": {"http": {"path": "/v1/chat/completions"},
                                "authorizer": {"iam": {"userArn":
                                    "arn:aws:sts::111122223333:assumed-role/lab-tenant-a/session"}}},
             "headers": {}, "body": json.dumps({"model": "standard", "messages": MSG})}
    r = lambda_handler.handle(event, None)
    assert r["statusCode"] == 200
    event["requestContext"]["authorizer"] = {}
    assert lambda_handler.handle(event, None)["statusCode"] == 401


def test_data_class_matrix_blocks_regulated_on_standard(gw):
    status, _, body = gw.chat(KEY_B, {"x-platform-data-class": "regulated"}, {"model": "standard", "messages": MSG})
    assert status == 403 and body["error"] == "matrix_blocked"
    assert gw.chat(KEY_B, {"x-platform-data-class": "confidential"}, {"model": "standard", "messages": MSG})[0] == 200


def test_unpriced_model_is_rejected_at_load(cfg):
    aliases = dict(cfg.aliases)
    aliases["standard"] = dict(aliases["standard"], local={"model": "mock/model-zzz"})
    with pytest.raises(ConfigError, match="no price"):
        Config(aliases, cfg.tenants, cfg.prices, "local", cfg.regions)
