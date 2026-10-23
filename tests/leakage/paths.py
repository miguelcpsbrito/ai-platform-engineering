"""Adapters for every registered retrieval path (tenancy/registry/retrieval-paths.yaml).

Each adapter exposes retrieve(query, identity) -> list[Hit], however the real path is
reached (library call, HTTP-style endpoint, cache, export). The leakage test attacks
all of them identically.
"""
from __future__ import annotations

import pathlib
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tenancy"))
from platform_retrieval import Hit, Identity, Retriever, Unauthorized  # noqa: E402


class LibraryPath:
    def __init__(self, retriever: Retriever):
        self.r = retriever

    def retrieve(self, query, identity):
        return self.r.retrieve(query, identity=identity)


class ForgedFilterPath(LibraryPath):
    """A caller that 'helpfully' passes the other tenant's ID. It must be ignored."""

    def __init__(self, retriever, other_tenant_id):
        super().__init__(retriever)
        self.other = other_tenant_id

    def retrieve(self, query, identity):
        return self.r.retrieve(query, identity=identity, tenant=self.other, filter={"tenant_id": self.other})


class HttpEndpointPath:
    """The RAG service endpoint: the verified identity arrives as a mesh-set header."""

    def __init__(self, retriever):
        self.r = retriever

    def handle(self, query, headers: dict):
        role = headers.get("x-platform-identity")
        if not role or not role.startswith("arn:aws:iam::"):
            raise Unauthorized("missing or malformed identity header")
        return self.r.retrieve(query, identity=Identity(role))

    def retrieve(self, query, identity=None, headers=None):
        if headers is None:
            headers = {"x-platform-identity": identity.role_arn} if identity else {}
        return self.handle(query, headers)


class CachePath:
    """Exact cache in front of retrieval. Keys include the tenant, so B's cached answers
    can never be served to A (the cache leak of Section 5.4)."""

    def __init__(self, retriever, directory):
        self.r = retriever
        self.directory = directory
        self.cache: dict = {}

    def retrieve(self, query, identity):
        tenant = self.directory.tenant_for(identity)
        key = (tenant, query)
        if key not in self.cache:
            self.cache[key] = self.r.retrieve(query, identity=identity)
        return self.cache[key]


class ExportPath:
    """The observability layer's sample export: every retrieval is recorded, and an
    export returns recorded hits — scoped to the caller's tenant."""

    def __init__(self, retriever, directory):
        self.r = retriever
        self.directory = directory
        self.recorded: list[tuple[str, Hit]] = []

    def record(self, query, identity):
        tenant = self.directory.tenant_for(identity)
        for h in self.r.retrieve(query, identity=identity):
            self.recorded.append((tenant, h))

    def retrieve(self, query, identity):
        tenant = self.directory.tenant_for(identity)
        return [h for t, h in self.recorded if t == tenant and query.split()[0].lower() in h.text.lower()] \
            or [h for t, h in self.recorded if t == tenant][:8]


def registered_paths() -> list[dict]:
    return yaml.safe_load((ROOT / "tenancy" / "registry" / "retrieval-paths.yaml").read_text())["paths"]
