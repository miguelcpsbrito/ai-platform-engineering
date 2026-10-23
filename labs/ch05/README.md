# Lab ch05 — Build it, then try to break it (Section 5.7)

The chapter's deliverable is a proof: the leakage test.

## Local track

```bash
pytest tests/leakage -q                                         # in-memory shared index
PLATFORM_PG_DSN="host=... user=postgres dbname=..." pytest tests/leakage -q   # + pgvector/RLS track
```

Two tenants with deliberately overlapping corpora and one canary each; as tenant A, the
suite attacks tenant B's canary through every path registered in
`tenancy/registry/retrieval-paths.yaml` — the library, a forged filter, the RAG endpoint,
the exact cache, the observability export, and Postgres RLS — and through the sloppy
paths (missing, malformed and claimed-but-unverified identity headers). It also proves
it can fail (`test_the_harness_detects_a_leaky_path`), and that `SET LOCAL` does not
carry a tenant across transactions on a pooled connection.

## AWS track

Apply `tenancy/terraform/vector-index` (OpenSearch Serverless, VPC-only), ingest both
corpora with `tenant_id` on every chunk, register an `opensearch` path that uses
`platform_retrieval.OpenSearchStore`, and run the same suite. Then the promotion drill
with [migration.md](migration.md) in miniature: move tenant B to a dedicated index,
shadow-compare retrieval, cut over at the gateway, re-run the suite, and delete the old
rows with the deletion pipeline (`governance/platform_governance.delete_subject`),
keeping its completion report as the lab artifact.

## Second round

Give a colleague who did not build the retrieval path one hour to retrieve tenant B's
canary as tenant A by any means an application developer has. Every path they find
becomes a new entry in the registry and a new case in the suite.
