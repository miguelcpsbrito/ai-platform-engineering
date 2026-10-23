"""The platform SDK (Section 8.3, Figure 8.3): application code calls gateway.chat; the
SDK opens the span, sets the GenAI semantic-convention attributes plus the platform
namespace, and propagates trace context to the gateway. Content (prompts, completions)
is never put on spans — sampled content goes to the harness store instead (Table 8.3).
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass

from opentelemetry import trace
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

tracer = trace.get_tracer("platform-sdk")


@dataclass
class Usage:
    input: int
    output: int


@dataclass
class ChatResponse:
    text: str
    model: str            # what served it (from the gateway's response header)
    usage: Usage
    cost_usd: float | None
    trace_id: str
    status: int


@dataclass
class Context:
    tenant: str
    feature: str
    conversation: str | None = None


class Gateway:
    def __init__(self, url: str | None = None, credential: str | None = None, ctx: Context | None = None,
                 prices: dict | None = None):
        self.url = (url or os.environ.get("PLATFORM_URL", "http://127.0.0.1:8080")).rstrip("/")
        self.credential = credential or os.environ.get("PLATFORM_KEY", "")
        self.ctx = ctx
        self.prices = prices or {}

    def _post(self, body: dict, headers: dict):
        req = urllib.request.Request(self.url + "/v1/chat/completions", data=json.dumps(body).encode(),
                                     headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.status, {k.lower(): v for k, v in r.headers.items()}, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, {k.lower(): v for k, v in e.headers.items()}, json.loads(e.read() or b"{}")

    def chat(self, messages: list[dict], alias: str = "standard", max_tokens: int = 512) -> ChatResponse:
        ctx = self.ctx
        with tracer.start_as_current_span(f"chat {alias}", kind=trace.SpanKind.CLIENT) as span:
            span.set_attribute("gen_ai.operation.name", "chat")
            span.set_attribute("gen_ai.request.model", alias)
            span.set_attribute("gen_ai.request.max_tokens", max_tokens)
            span.set_attribute("platform.tenant", ctx.tenant)
            span.set_attribute("platform.feature", ctx.feature)
            headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.credential}",
                       "x-platform-feature": ctx.feature}
            if ctx.conversation:
                headers["x-platform-conversation"] = ctx.conversation
                span.set_attribute("gen_ai.conversation.id", ctx.conversation)
            TraceContextTextMapPropagator().inject(headers)
            status, h, body = self._post({"model": alias, "messages": messages, "max_tokens": max_tokens}, headers)
            span.set_attribute("http.response.status_code", status)
            if status != 200:
                span.set_status(trace.Status(trace.StatusCode.ERROR, body.get("error", "error")))
                span.set_attribute("error.type", body.get("error", str(status)))
                return ChatResponse("", "", Usage(0, 0), None, h.get("x-platform-trace-id", ""), status)
            served = h.get("x-platform-served-by", "")
            usage = Usage(body["usage"]["prompt_tokens"], body["usage"]["completion_tokens"])
            span.set_attribute("gen_ai.response.model", served)
            span.set_attribute("gen_ai.usage.input_tokens", usage.input)
            span.set_attribute("gen_ai.usage.output_tokens", usage.output)
            span.set_attribute("platform.fallback", h.get("x-platform-fallback") == "true")
            cost = None
            p = self.prices.get(served.split("/", 1)[-1])
            if p:
                cost = (usage.input * p["input"] + usage.output * p["output"]) / 1e6
                span.set_attribute("platform.cost_usd", cost)
            return ChatResponse(body["choices"][0]["message"]["content"], served, usage, cost,
                                h.get("x-platform-trace-id", ""), status)
