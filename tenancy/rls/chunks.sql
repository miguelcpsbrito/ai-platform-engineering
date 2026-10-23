-- tenancy/rls/chunks.sql — the shared chunks table hardened with row-level security
-- (Section 5.4, Figure 5.7). Apply as the schema owner; the application connects as
-- platform_app, which owns nothing and is not BYPASSRLS.

CREATE TABLE IF NOT EXISTS chunks (
  id         bigserial PRIMARY KEY,
  tenant_id  uuid        NOT NULL,
  doc_id     text        NOT NULL,
  content    text        NOT NULL,
  embedding  vector(1024),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS chunks_tenant ON chunks (tenant_id);
CREATE INDEX IF NOT EXISTS chunks_embedding ON chunks USING hnsw (embedding vector_cosine_ops);

-- pgvector, shared index hardened with row-level security
ALTER TABLE chunks ENABLE ROW LEVEL SECURITY;
-- the table owner is bound too
ALTER TABLE chunks FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON chunks
  USING (tenant_id = NULLIF(
         current_setting('app.tenant_id', true), '')::uuid);
-- unset → NULL → no rows: the policy fails closed
-- the application role owns nothing and is not BYPASSRLS
-- (NULLIF: on a pooled connection the setting reads '' after an earlier SET LOCAL)

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'platform_app') THEN
    CREATE ROLE platform_app LOGIN NOBYPASSRLS;
  END IF;
END $$;
GRANT SELECT, INSERT, DELETE ON chunks TO platform_app;
GRANT USAGE ON SEQUENCE chunks_id_seq TO platform_app;
