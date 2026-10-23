"""The platform retrieval library (Section 5.4): every retrieval goes through here, and
the tenant filter comes from verified identity — never from a parameter the caller
can forget, omit or forge.

Engines:
  InMemoryIndex      local labs and unit tests (a shared index, deliberately)
  opensearch_query   builds the filtered k-NN body of Figure 5.8 for OpenSearch
  PgvectorStore      Postgres with RLS (Figure 5.7); SET LOCAL per transaction
"""
from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass

DIM = 1024


class Unauthorized(PermissionError):
    pass


@dataclass(frozen=True)
class Hit:
    tenant_id: str
    doc_id: str
    text: str
    score: float


@dataclass(frozen=True)
class Identity:
    """A verified workload identity, as the gateway or the service mesh asserts it."""
    role_arn: str


class TenantDirectory:
    """Maps verified identities to tenant IDs, from the tenant records (gateway/tenants)."""

    def __init__(self, bindings: dict[str, str]):
        self.bindings = bindings            # role ARN → tenant UUID

    @classmethod
    def from_gateway_config(cls, cfg) -> "TenantDirectory":
        out = {}
        for t in cfg.tenants.values():
            tid = t.raw.get("id")
            for key in ("workload_role", "pod_identity_role"):
                arn = t.identities.get(key)
                if tid and arn:
                    out[arn] = tid
        return cls(out)

    def tenant_for(self, identity: Identity | None) -> str:
        if identity is None or not identity.role_arn:
            raise Unauthorized("no verified identity")
        try:
            return self.bindings[identity.role_arn]
        except KeyError:
            raise Unauthorized(f"identity {identity.role_arn} is not bound to a tenant") from None


def embed(text: str, dim: int = DIM) -> list[float]:
    """Deterministic hashing embedding: good enough to make retrieval and leaks real."""
    v = [0.0] * dim
    for tok in re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", text.lower()):
        h = int(hashlib.blake2b(tok.encode(), digest_size=8).hexdigest(), 16)
        v[h % dim] += 1.0 if (h >> 63) & 1 else -1.0
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def cosine(a, b) -> float:
    return sum(x * y for x, y in zip(a, b))


class InMemoryIndex:
    """One shared index for all tenants, with tenant_id on every chunk (isolation level 1)."""

    def __init__(self):
        self.rows: list[tuple[str, str, str, list[float]]] = []

    def add(self, tenant_id: str, doc_id: str, text: str) -> None:
        self.rows.append((tenant_id, doc_id, text, embed(text)))

    def search(self, query: str, k: int, tenant_filter: str | None) -> list[Hit]:
        q = embed(query)
        rows = [r for r in self.rows if tenant_filter is None or r[0] == tenant_filter]
        scored = sorted(((cosine(q, r[3]), r) for r in rows), key=lambda x: -x[0])[:k]
        return [Hit(r[0], r[1], r[2], s) for s, r in scored]

    def delete_where(self, tenant_id: str, predicate) -> int:
        before = len(self.rows)
        self.rows = [r for r in self.rows if not (r[0] == tenant_id and predicate(r[2]))]
        return before - len(self.rows)


class Retriever:
    """The only supported way to query a shared index."""

    def __init__(self, index, directory: TenantDirectory, k: int = 8):
        self.index = index
        self.directory = directory
        self.k = k

    def retrieve(self, query: str, identity: Identity | None, k: int | None = None, **_ignored) -> list[Hit]:
        # Any caller-supplied 'tenant' or 'filter' arrives in **_ignored and is dropped:
        # the filter is derived, not accepted.
        tenant = self.directory.tenant_for(identity)
        return self.index.search(query, k or self.k, tenant_filter=tenant)


def opensearch_query(vector: list[float], identity: Identity, directory: TenantDirectory,
                     k: int = 8) -> dict:
    """Figure 5.8: the tenant filter sits inside the k-NN clause (efficient filtering),
    and its value comes from verified identity."""
    tenant = directory.tenant_for(identity)
    return {
        "size": k,
        "query": {
            "knn": {
                "embedding": {
                    "vector": vector,
                    "k": k,
                    "filter": {"term": {"tenant_id": tenant}},
                }
            }
        },
    }


class PgvectorStore:
    """Postgres + pgvector behind RLS. Each query is one transaction with SET LOCAL, so a
    pooled connection never carries a tenant into the next request (Figure 5.7)."""

    def __init__(self, conninfo: str, directory: TenantDirectory, has_vector: bool = True):
        import psycopg
        self.psycopg = psycopg
        self.conninfo = conninfo
        self.directory = directory
        self.has_vector = has_vector

    def search(self, query: str, k: int, tenant_filter: str | None) -> list[Hit]:
        with self.psycopg.connect(self.conninfo) as conn, conn.transaction():
            cur = conn.cursor()
            if tenant_filter is not None:
                cur.execute("SELECT set_config('app.tenant_id', %s, true)", (tenant_filter,))
            if self.has_vector:
                cur.execute("SET LOCAL hnsw.iterative_scan = relaxed_order")
                cur.execute("SELECT tenant_id::text, doc_id, content, 1 - (embedding <=> %s::vector) "
                            "FROM chunks ORDER BY embedding <=> %s::vector LIMIT %s",
                            (str(embed(query)), str(embed(query)), k))
            else:  # local fallback without the extension: RLS is still what is under test
                cur.execute("SELECT tenant_id::text, doc_id, content, 0.0 FROM chunks "
                            "ORDER BY similarity_fallback(content, %s) DESC LIMIT %s", (query, k))
            return [Hit(r[0], r[1], r[2], float(r[3])) for r in cur.fetchall()]


class OpenSearchStore:
    """OpenSearch (managed or Serverless) with the filtered k-NN query of Figure 5.8.
    `client` is an opensearch-py OpenSearch client signed with SigV4 (AWSV4SignerAuth,
    service "aoss" for Serverless, "es" for managed domains)."""

    def __init__(self, client, index: str, directory: TenantDirectory):
        self.client, self.index, self.directory = client, index, directory

    @classmethod
    def connect(cls, host: str, index: str, directory: TenantDirectory, region: str, service: str = "aoss"):
        import boto3
        from opensearchpy import AWSV4SignerAuth, OpenSearch, RequestsHttpConnection
        auth = AWSV4SignerAuth(boto3.Session().get_credentials(), region, service)
        client = OpenSearch(hosts=[{"host": host, "port": 443}], http_auth=auth, use_ssl=True,
                            verify_certs=True, connection_class=RequestsHttpConnection)
        return cls(client, index, directory)

    def search(self, query: str, k: int, tenant_filter: str | None) -> list[Hit]:
        if tenant_filter is None:
            raise Unauthorized("OpenSearchStore never runs an unfiltered query")
        body = {"size": k, "_source": ["tenant_id", "doc_id", "content"],
                "query": {"knn": {"embedding": {"vector": embed(query), "k": k,
                                                "filter": {"term": {"tenant_id": tenant_filter}}}}}}
        res = self.client.search(index=self.index, body=body)
        return [Hit(h["_source"]["tenant_id"], h["_source"]["doc_id"], h["_source"]["content"], h["_score"])
                for h in res["hits"]["hits"]]


# --- restore drill support (Section 9.6) ---------------------------------------------------

def snapshot(index: InMemoryIndex) -> list[dict]:
    return [{"tenant_id": t, "doc_id": d, "text": x} for t, d, x, _ in index.rows]


def restore(rows: list[dict]) -> InMemoryIndex:
    idx = InMemoryIndex()
    for r in rows:
        idx.add(r["tenant_id"], r["doc_id"], r["text"])
    return idx


def retrieval_diff(a, b, probes: list[tuple[str, str]], k: int = 8) -> dict:
    """Compare top-k doc IDs per (tenant, query) probe between two engines. A restore is
    proven by identical retrieval, not by a row count."""
    mismatches = []
    for tenant, q in probes:
        ra = [h.doc_id for h in a.search(q, k, tenant)]
        rb = [h.doc_id for h in b.search(q, k, tenant)]
        if ra != rb:
            mismatches.append({"tenant": tenant, "query": q, "before": ra, "after": rb})
    return {"probes": len(probes), "mismatches": mismatches}
