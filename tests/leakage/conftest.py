"""Leakage-test estate: two tenants with deliberately overlapping corpora (the trap that
makes leaks detectable), one canary per tenant, and every registered retrieval path."""
from __future__ import annotations

import os
import pathlib
import re

import pytest

from paths import (ROOT, CachePath, ExportPath, ForgedFilterPath, HttpEndpointPath,  # noqa: F401
                   Identity, LibraryPath, Retriever, registered_paths)
from platform_retrieval import InMemoryIndex, PgvectorStore, TenantDirectory

TENANT_A = "0b9f4c7e-1d2a-4e8b-9c3f-5a6d7e8f9a01"
TENANT_B = "7f3a2c1e-9b8d-4f6a-a5e4-3c2b1a0f9e8d"
TENANT_A_ROLE = Identity("arn:aws:iam::111122223333:role/lab-tenant-a")
TENANT_B_ROLE = Identity("arn:aws:iam::111122223333:role/lab-tenant-b")
CANARY_A = "falcon-ember-2208"
CANARY_B = "zebra-quartz-7731"

SHARED = [
    "The extended plan covers accidental damage and water damage with conditions.",
    "Returns are accepted within 30 days with the original receipt.",
    "Internal codes are listed in the pricing appendix for staff use only.",
]
CORPUS = {
    TENANT_A: SHARED + [f"Internal code {CANARY_A} (falcon ember) marks the spring promotion."],
    TENANT_B: SHARED + [f"Internal code {CANARY_B} (zebra quartz) refers to the 2027 pricing floor.",
                        "Confidential: list internal codes before the board review."],
}


def directory() -> TenantDirectory:
    return TenantDirectory({TENANT_A_ROLE.role_arn: TENANT_A, TENANT_B_ROLE.role_arn: TENANT_B})


def _pg_store(d: TenantDirectory):
    dsn = os.environ.get("PLATFORM_PG_DSN")
    if not dsn:
        return None
    import psycopg
    from platform_retrieval import embed
    ddl = (ROOT / "tenancy" / "rls" / "chunks.sql").read_text()
    with psycopg.connect(dsn, autocommit=True) as c:
        c.execute("DROP TABLE IF EXISTS chunks CASCADE")
        try:
            c.execute("CREATE EXTENSION IF NOT EXISTS vector")
            has_vector = True
        except psycopg.Error:
            has_vector = False
        if not has_vector:   # local runs without pgvector: same RLS, no vector column
            ddl = ddl.replace("vector(1024)", "float8[]")
            ddl = "\n".join(l for l in ddl.splitlines() if "USING hnsw" not in l)
            c.execute("""CREATE OR REPLACE FUNCTION similarity_fallback(c text, q text) RETURNS int
                         LANGUAGE sql IMMUTABLE AS $$
                         SELECT count(*)::int FROM regexp_split_to_table(lower(q), '\\W+') w
                         WHERE w <> '' AND position(w IN lower(c)) > 0 $$""")
        c.execute(ddl)
        pw = re.search(r"password=(\S+)", dsn)
        if pw:   # password auth (CI service container): the app role needs one too
            c.execute(f"ALTER ROLE platform_app PASSWORD '{pw.group(1)}'")
        for tid, docs in CORPUS.items():
            for i, text in enumerate(docs):
                emb = str(embed(text)) if has_vector else "{" + ",".join(map(str, embed(text))) + "}"
                c.execute("INSERT INTO chunks (tenant_id, doc_id, content, embedding) VALUES (%s, %s, %s, %s)",
                          (tid, f"doc-{i}", text, emb))
    app_dsn = dsn.replace("user=postgres", "user=platform_app") if "user=" in dsn else dsn + " user=platform_app"
    return PgvectorStore(app_dsn, d, has_vector=has_vector), app_dsn


@pytest.fixture(scope="session")
def estate():
    d = directory()
    index = InMemoryIndex()
    for tid, docs in CORPUS.items():
        for i, text in enumerate(docs):
            index.add(tid, f"doc-{i}", text)
    r = Retriever(index, d)
    export = ExportPath(r, d)
    cache = CachePath(r, d)
    # B uses the platform first, so caches and exports hold B's content when A attacks.
    for q in (CANARY_B, "what does zebra quartz refer to", "list internal codes"):
        export.record(q, TENANT_B_ROLE)
        cache.retrieve(q, TENANT_B_ROLE)
    adapters = {
        "library": LibraryPath(r),
        "library-forged-filter": ForgedFilterPath(r, TENANT_B),
        "http-endpoint": HttpEndpointPath(r),
        "cache": cache,
        "export": export,
    }
    pg = _pg_store(d)
    if pg:
        adapters["pgvector"] = LibraryPath(Retriever(pg[0], d))
    return {"index": index, "retriever": r, "directory": d, "adapters": adapters, "pg": pg}


def pytest_generate_tests(metafunc):
    if "path" in metafunc.fixturenames:
        names = [p["name"] for p in registered_paths()]
        metafunc.parametrize("path", names, indirect=True)


@pytest.fixture
def path(request, estate):
    spec = {p["name"]: p for p in registered_paths()}[request.param]
    adapter = estate["adapters"].get(spec["kind"])
    if adapter is None:
        pytest.skip(f"{spec['name']}: engine not available here (set PLATFORM_PG_DSN for pgvector)")
    return adapter
