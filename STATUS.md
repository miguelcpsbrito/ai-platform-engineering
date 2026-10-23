# Status — release 0.1.0 (October 2026)

143 tests pass offline (plus 4 live SCP tests that need a test-OU account), and the
local tracks of seven labs run end to end in CI.

Three levels of evidence, stated per module:

- **Tested offline** — unit and integration tests that run in CI with no AWS account
  (simulated models, DuckDB, local Postgres, botocore request validation).
- **Validated** — Terraform parsed, formatted and checked against the AWS provider 6.x
  schema; `terraform validate` runs in CI.
- **Applied on AWS** — deployed to a real account, proofs run, torn down, with the date.

**Nothing in this release has been applied on AWS yet.** The `aws-labs` workflow
(manual, OIDC into a sandbox account) is how that column gets filled; each run updates
this table and the lab's `CURRENT.md`.

| Module | Implemented | Tested offline | Validated | Applied on AWS | Known gaps |
|---|---|---|---|---|---|
| `org/` | 3 SCPs, tag policy, OUs | 25 policy tests (missing-key semantics, size limits) | yes | not yet | Live suite `tests/scp` ready, not yet run |
| `network/` | Hub, endpoints, DNS Firewall, Network Firewall track, Transit Gateway (optional, RAM share) | — | yes | not yet | Spoke-side attachments belong in the tenant baseline; not yet included |
| `identity/` | Gateway role, boundary, approver, break-glass, Identity Center | boundary via org oracle | yes | not yet | — |
| `gateway/` | Alias map, tenants, custom gateway, fallback, exact cache, quotas, 429 contract, matrix, metering, fault layer, LiteLLM renderer | 26 unit + 11 conformance; rendered config loads in LiteLLM 1.85 Router | yes (profiles, stub, proxy) | not yet | No streaming in the custom gateway; LiteLLM does not pass Bedrock service tiers; conformance not yet run against LiteLLM |
| `tenancy/` | Schema, retrieval library (in-memory, pgvector RLS, OpenSearch), registry, baseline, vector index | 8 unit + 30 leakage (incl. Postgres RLS) | yes | not yet | OpenSearch path tested against a fake client only |
| `finops/` | DDL, allocation (5 steps), reconciliation, lever ranking, dashboard queries, anomaly, weekly message, TCO, cost-model spreadsheet, Data Exports + Firehose | 16 tests on a synthetic month | yes | not yet | QuickSight dashboards not included |
| `observability/` | SDK, harness, detector, calibration, suite runner, collector config, persona dashboard specs | 5 tests | n/a | not yet | No Terraform for the collector and LLM-observability layer yet; dashboards are specifications, not rendered |
| `governance/` | Tiering, guardrails (Terraform), red team, matrix, deletion, audit, controls matrix, OWASP LLM 2025 mapping | 11 tests | yes | not yet | Layer 1 is a local stand-in offline; Bedrock adapter not yet run |
| `blueprints/` | RAG (full anatomy); agent, chatbot, batch (seed) | via ch07 lab | n/a | not yet | Canary step is deployer-specific (documented) |
| `agents/` | Registry, budgets, kill switch, approvals, credentials | 9 tests | n/a | not yet | No AgentCore deployment module; readiness item 6 not covered |
| `portal/` | Thin portal | via ch07 lab | n/a | n/a | Backstage track is documented, not packaged |
| `sre/` | RB-1 … RB-5 | game day uses RB-2 | n/a | n/a | — |
