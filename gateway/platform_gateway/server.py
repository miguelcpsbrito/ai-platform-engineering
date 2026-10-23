"""Local HTTP server for the platform API contract (labs, conformance suite).

    python -m platform_gateway.server --mock --port 8080

Local mode authenticates with per-tenant lab API keys (Authorization: Bearer <key>),
standing in for workload identity. Never expose this server beyond localhost: the
AWS deployment authenticates with IAM (lambda_handler.py) or Pod Identity (the proxy).
"""
from __future__ import annotations

import argparse
import json
import pathlib
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .backends import BedrockBackend, MockBackend
from .config import GATEWAY_DIR, Config
from .faults import FaultLayer
from .handler import Gateway
from .metering import sink_from_settings


def build(mock: bool = True, environment: str | None = None, base=GATEWAY_DIR, sink=None) -> tuple[Gateway, FaultLayer]:
    cfg = Config.load(base, environment=environment or ("local" if mock else None))
    faults = FaultLayer(MockBackend() if mock else BedrockBackend())
    gw = Gateway(cfg, faults, sink=sink or sink_from_settings(cfg.settings))
    return gw, faults


class Handler(BaseHTTPRequestHandler):
    gateway: Gateway = None
    faults: FaultLayer = None
    admin_enabled = True
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # quiet by default
        pass

    def _send(self, status: int, headers: dict, body: dict) -> None:
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        for k, v in headers.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b"{}"
        try:
            return json.loads(raw or b"{}")
        except json.JSONDecodeError:
            return {"__invalid__": True}

    def do_GET(self):
        if self.path == "/healthz":
            return self._send(200, {}, {"status": "ok", "environment": self.gateway.config.environment})
        if self.path == "/v1/models":
            ident = self._identity()
            try:
                t = self.gateway.authenticate(ident)
            except Exception:
                return self._send(401, {}, {"error": "unauthenticated"})
            return self._send(200, {}, {"object": "list", "data": [
                {"id": a, "object": "model", "owned_by": "platform"} for a in t.aliases]})
        return self._send(404, {}, {"error": "not_found"})

    def do_POST(self):
        try:
            self._post()
        except Exception as e:  # never drop the connection: answer with the contract's error shape
            self._send(500, {}, {"error": "internal_error", "message": type(e).__name__})

    def _post(self):
        body = self._body()
        if self.path == "/v1/chat/completions":
            if body.get("__invalid__"):
                return self._send(400, {}, {"error": "invalid_request", "message": "body is not JSON"})
            status, headers, resp = self.gateway.chat(self._identity(), dict(self.headers), body)
            return self._send(status, headers, resp)
        if self.path.startswith("/admin/") and self.admin_enabled:
            return self._admin(body)
        return self._send(404, {}, {"error": "not_found"})

    def _identity(self) -> dict:
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return {"kind": "api_key", "value": auth[7:].strip()}
        return {}

    def _admin(self, body: dict):
        """Lab-only control plane: fault injection and config reload (never in AWS mode)."""
        if self.path == "/admin/faults":
            self.faults.load(body.get("rules", []))
            return self._send(200, {}, {"rules": len(self.faults.rules)})
        if self.path == "/admin/faults/clear":
            self.faults.clear()
            return self._send(200, {}, {"rules": 0})
        if self.path == "/admin/reload":
            try:
                cfg = Config.load(body.get("base") or GATEWAY_DIR, environment=self.gateway.config.environment,
                                  overlay=body.get("overlay"))
            except ValueError as e:     # a bad config is rejected; the running one keeps serving
                return self._send(400, {}, {"reloaded": False, "error": str(e)})
            self.gateway.config = cfg
            return self._send(200, {}, {"reloaded": True, "environment": cfg.environment})
        return self._send(404, {}, {"error": "not_found"})


def serve(port: int = 8080, mock: bool = True, environment: str | None = None, base=GATEWAY_DIR,
          sink=None, background: bool = False):
    gw, faults = build(mock, environment, base, sink)
    handler = type("BoundHandler", (Handler,), {"gateway": gw, "faults": faults, "admin_enabled": mock})
    httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
    if background:
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        return httpd, gw, faults
    print(f"platform gateway on http://127.0.0.1:{httpd.server_port} "
          f"(environment={gw.config.environment}, mock={mock})")
    httpd.serve_forever()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--mock", action="store_true", help="simulated models, no AWS calls")
    ap.add_argument("--env", default=None)
    ap.add_argument("--config", default=str(GATEWAY_DIR))
    a = ap.parse_args()
    serve(a.port, a.mock, a.env, pathlib.Path(a.config))


if __name__ == "__main__":
    main()
