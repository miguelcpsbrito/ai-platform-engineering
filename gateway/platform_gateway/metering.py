"""Metering (responsibility 8, Section 4.2): one event per model interaction.

The event schema is the contract with finops/ (Chapter 6): gateway events are the
granular truth that allocation joins to the CUR. Content never appears in an event.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import threading

EVENT_FIELDS = (
    "ts", "trace_id", "tenant", "feature", "convo_id", "alias", "provider", "model",
    "region", "tier", "status", "fallback", "attempts", "cache_hit", "tokens_in",
    "tokens_out", "tokens_cached", "cost_usd", "latency_ms", "config_version",
    "environment", "faults",
)


def make_event(**kw) -> dict:
    ev = {k: kw.get(k) for k in EVENT_FIELDS}
    ev["ts"] = ev["ts"] or dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds")
    return ev


class StdoutSink:
    """CloudWatch Logs picks up stdout in Lambda and on EKS (via the collector)."""

    def emit(self, event: dict) -> None:
        sys.stdout.write(json.dumps({"platform_metering": event}) + "\n")
        sys.stdout.flush()


class FileSink:
    def __init__(self, path: str):
        self.path = path
        self.lock = threading.Lock()

    def emit(self, event: dict) -> None:
        with self.lock, open(self.path, "a") as f:
            f.write(json.dumps(event) + "\n")


class FirehoseSink:
    """Firehose → S3 (Parquet via the delivery stream's record conversion) for finops/."""

    def __init__(self, stream: str, client=None):
        import boto3
        self.stream = stream
        self.client = client or boto3.client("firehose")

    def emit(self, event: dict) -> None:
        self.client.put_record(DeliveryStreamName=self.stream,
                               Record={"Data": (json.dumps(event) + "\n").encode()})


class MemorySink:
    def __init__(self):
        self.events: list[dict] = []

    def emit(self, event: dict) -> None:
        self.events.append(event)


def sink_from_settings(settings: dict):
    m = settings.get("metering", {})
    kind = os.environ.get("PLATFORM_METERING_SINK", m.get("sink", "stdout"))
    if kind == "file":
        return FileSink(os.environ.get("PLATFORM_METERING_FILE", m.get("file", "metering.jsonl")))
    if kind == "firehose":
        return FirehoseSink(os.environ.get("PLATFORM_METERING_STREAM", m.get("firehose_stream")))
    if kind == "memory":
        return MemorySink()
    return StdoutSink()
