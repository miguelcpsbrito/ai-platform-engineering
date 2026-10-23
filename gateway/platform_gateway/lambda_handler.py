"""AWS Lambda entry point for the minimal platform's gateway stub (Section 3.6, step 4).

The function URL uses AWS_IAM auth, so the caller's role ARN arrives already verified in
requestContext.authorizer.iam — workload identity with no keys (responsibility 1).
"""
from __future__ import annotations

import base64
import json
import os
import pathlib

from .backends import BedrockBackend
from .config import Config
from .faults import FaultLayer
from .handler import Gateway
from .metering import sink_from_settings

_GW: Gateway | None = None


def _gateway() -> Gateway:
    global _GW
    if _GW is None:
        base = pathlib.Path(os.environ.get("PLATFORM_CONFIG_DIR", pathlib.Path(__file__).resolve().parents[1]))
        cfg = Config.load(base)
        cfg.version = os.environ.get("PLATFORM_CONFIG_VERSION", cfg.version)
        _GW = Gateway(cfg, FaultLayer(BedrockBackend()), sink=sink_from_settings(cfg.settings))
    return _GW


def handle(event, ctx):
    gw = _gateway()
    rc = event.get("requestContext", {})
    path = rc.get("http", {}).get("path", event.get("rawPath", "/"))
    if path == "/healthz":
        return _resp(200, {}, {"status": "ok"})
    if path != "/v1/chat/completions":
        return _resp(404, {}, {"error": "not_found"})
    caller = rc.get("authorizer", {}).get("iam", {}).get("userArn")
    identity = {"kind": "iam", "value": caller} if caller else {}
    raw = event.get("body") or "{}"
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode()
    try:
        body = json.loads(raw)
    except json.JSONDecodeError:
        return _resp(400, {}, {"error": "invalid_request", "message": "body is not JSON"})
    status, headers, resp = gw.chat(identity, event.get("headers", {}), body)
    return _resp(status, headers, resp)


def _resp(status, headers, body):
    return {"statusCode": status, "headers": dict({"content-type": "application/json"}, **headers),
            "body": json.dumps(body)}
