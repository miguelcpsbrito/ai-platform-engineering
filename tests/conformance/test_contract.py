"""The platform API contract (Figure 4.8), as executable assertions. A gateway that
passes this suite can replace another without any application changing — which is the
whole anti-lock-in argument of Section 4.7. Run it on every gateway config or image
change, and daily against production (Table A.3)."""
import json
import urllib.error
import urllib.request

import pytest

MSG = [{"role": "user", "content": "Reply with one word: ready"}]


def post(gw, body, key="a", headers=None, raw=None):
    h = {"Content-Type": "application/json"}
    if key:
        h["Authorization"] = f"Bearer {gw['key_' + key] if key in ('a', 'b') else key}"
    h.update(headers or {})
    data = raw if raw is not None else json.dumps(body).encode()
    req = urllib.request.Request(gw["url"] + "/v1/chat/completions", data=data, headers=h, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, {k.lower(): v for k, v in r.headers.items()}, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in e.headers.items()}, json.loads(e.read() or b"{}")


def test_chat_completion_wire_shape(gateway):
    status, _, body = post(gateway, {"model": "standard", "messages": MSG, "max_tokens": 32})
    assert status == 200
    assert body["object"] == "chat.completion"
    assert body["choices"][0]["message"]["role"] == "assistant"
    assert isinstance(body["choices"][0]["message"]["content"], str)
    for k in ("prompt_tokens", "completion_tokens", "total_tokens"):
        assert isinstance(body["usage"][k], int)


def test_response_speaks_aliases_not_provider_ids(gateway):
    _, _, body = post(gateway, {"model": "standard", "messages": MSG})
    assert body["model"] == "standard"


def test_unauthenticated_requests_fail_closed(gateway):
    status, _, _ = post(gateway, {"model": "standard", "messages": MSG}, key=None)
    assert status == 401


def test_invalid_credentials_fail_closed(gateway):
    status, _, _ = post(gateway, {"model": "standard", "messages": MSG}, key="not-a-real-key")
    assert status == 401


def test_claimed_tenant_must_match_identity(gateway):
    status, _, _ = post(gateway, {"model": "standard", "messages": MSG},
                        headers={"x-platform-tenant": "someone-else"})
    assert status == 403


def test_alias_outside_entitlement_is_refused(gateway):
    status, _, body = post(gateway, {"model": "premium", "messages": MSG})   # tenant-a: no premium
    assert status == 403 and body.get("error")


def test_provider_model_ids_are_not_accepted(gateway):
    status, _, _ = post(gateway, {"model": "us.anthropic.claude-sonnet-4-6", "messages": MSG})
    assert status in (400, 403)


def test_malformed_body_is_400(gateway):
    status, _, _ = post(gateway, None, raw=b"{not json")
    assert status == 400
    status, _, _ = post(gateway, {"model": "standard"})
    assert status == 400


def test_trace_context_is_honoured(gateway):
    tp = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    _, headers, body = post(gateway, {"model": "standard", "messages": MSG}, headers={"traceparent": tp})
    trace = headers.get("x-platform-trace-id") or body.get("platform", {}).get("trace_id")
    assert trace == "4bf92f3577b34da6a3ce929d0e0e4736"


def test_quota_rejection_contract(gateway):
    """Figure 5.5: which limit, how far over, when to retry, where to ask for more."""
    big = [{"role": "user", "content": "x" * 60000}]
    for _ in range(4):
        status, headers, body = post(gateway, {"model": "standard", "messages": big, "max_tokens": 8000})
        if status == 429:
            break
    assert status == 429, "tenant-a's quota should be exhausted by four worst-case debits"
    assert int(headers["retry-after"]) >= 1
    for k in ("error", "limit", "window_s", "limit_value", "current", "class", "raise_request", "trace_id"):
        assert k in body, f"429 body missing {k}"


def test_models_endpoint_lists_entitlements(gateway):
    req = urllib.request.Request(gateway["url"] + "/v1/models",
                                 headers={"Authorization": f"Bearer {gateway['key_a']}"})
    with urllib.request.urlopen(req, timeout=10) as r:
        ids = {m["id"] for m in json.loads(r.read())["data"]}
    assert {"standard", "fast"} <= ids and "premium" not in ids
