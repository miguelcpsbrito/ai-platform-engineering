"""Egress probe for Table 3.5 step 2, run inside a workload subnet.

Resolves an external model provider (expected: NXDOMAIN from DNS Firewall) and the
Bedrock runtime endpoint (expected: a private address of the interface endpoint).
"""
import ipaddress
import os
import socket


def resolve(name):
    try:
        return sorted({a[4][0] for a in socket.getaddrinfo(name, 443)})
    except socket.gaierror as e:
        return f"error: {e}"


def handler(event, ctx):
    region = os.environ["AWS_REGION"]
    blocked = resolve(event.get("blocked", "api.openai.com"))
    bedrock = resolve(f"bedrock-runtime.{region}.amazonaws.com")
    private = isinstance(bedrock, list) and bool(bedrock) and all(
        ipaddress.ip_address(a).is_private for a in bedrock)
    return {"blocked_lookup": blocked, "bedrock_lookup": bedrock,
            "provider_blocked": isinstance(blocked, str), "bedrock_private": private}
