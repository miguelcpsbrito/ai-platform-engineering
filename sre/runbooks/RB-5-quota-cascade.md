# RB-5: I-5 quota exhaustion cascade                Owner: ai-platform SRE   Reviewed: 2026-10

**Trigger** — Shared-pool 429 rate > 2% across ≥ 2 tenants; Bedrock EstimatedTPMQuotaUsage > 90% for the account and model.

**Classify** — (1) 429 bodies (`limit`, `class`) by tenant: one tenant exhausting its own quota is not a cascade. (2) Account-level quota usage per model. (3) Which class is suffering: critical floors must hold.

**Decide** — Batch or standard traffic crowding critical: shed batch first, then queue standard (the ladder in tenant records). Account quota genuinely too low: request an increase and enable cross-region capacity.

**Act**
1. Degradation ladder: tenants with `cheaper_alias` move automatically; apply `queue` / `shed` per tenant record for batch class.
2. Move batch work to Bedrock batch inference or the Flex tier.
3. Service-quota increase request; record the case number.

**Verify** — Critical-class 429 rate zero; TTFT p95 for critical within contract.

**Communicate** — Tenant channel: which classes are queued or shed and until when.

**Close** — Postmortem for S1/S2; attach quota usage, 429 breakdown by class, and the ladder timeline.
