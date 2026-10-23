-- The per-request pattern (Figure 5.7). The platform library runs exactly this.
BEGIN;
-- per transaction: safe behind a pooler
SET LOCAL app.tenant_id = '7f3a2c1e-9b8d-4f6a-a5e4-3c2b1a0f9e8d';
SET LOCAL hnsw.iterative_scan = relaxed_order;   -- pgvector ≥ 0.8
SELECT content FROM chunks ORDER BY embedding <=> $1 LIMIT 8;
COMMIT;
