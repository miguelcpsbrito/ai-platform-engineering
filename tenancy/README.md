# tenancy/ — isolation you can prove (Chapter 5)

- `schema/tenant.schema.json` — the tenant record (Figures 5.3, 5.9, C.4); regulated data requires isolation level 3.
- `platform_retrieval/` — the only supported way to query a shared index: the tenant filter is derived from verified identity and caller-supplied filters are ignored. Engines: in-memory, Postgres + pgvector with RLS, OpenSearch (filtered k-NN, Figure 5.8). Snapshot, restore and retrieval diff for the restore drill.
- `rls/chunks.sql` — Figure 5.7, with the `NULLIF` that keeps pooled connections fail-closed.
- `registry/retrieval-paths.yaml` — every path that can reach retrieval; the leakage suite attacks each one.
- `terraform/{registry,baseline,vector-index}` — tenant registry table, the per-account baseline (KMS key, budget), an OpenSearch Serverless vector collection.

`pip install ./tenancy[pgvector,opensearch]` installs the library as `platform-retrieval`.
