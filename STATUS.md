# Status — release 0.1.0 (October 2026)

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
| `network/` | Hub, endpoints, DNS Firewall, Network Firewall track | — | yes | not yet | Transit Gateway attachment for spokes not included |
| `identity/` | Gateway role, boundary, approver, break-glass, Identity Center | boundary via org oracle | yes | not yet | — |
| `gateway/` | Alias map, tenants, custom gateway, fallback, exact cache, quotas, 429 contract, matrix, metering, fault layer, LiteLLM renderer | 25 unit + 11 conformance; rendered config loads in LiteLLM 1.85 Router | yes (profiles, stub, proxy) | not yet | No streaming in the custom gateway; LiteLLM does not pass Bedrock service tiers; conformance not yet run against LiteLLM |
| `tenancy/` | Schema, retrieval library (in-memory, pgvector RLS, OpenSearch), registry, baseline, vector index | 9 unit + 29 leakage (incl. Postgres RLS) | yes | not yet | OpenSearch path tested against a fake client only |
| `finops/` | DDL, allocation (5 steps), reconciliation, anomaly, weekly message, TCO, Data Exports + Firehose | 9 tests on a synthetic month | yes | not yet | QuickSight dashboards not included |
| `observability/` | SDK, harness, detector, calibration, suite runner, collector config | 5 tests | n/a | not yet | No Terraform for the collector and LLM-observability layer yet |
| `governance/` | Tiering, guardrails (Terraform), red team, matrix, deletion, audit | 11 tests | yes | not yet | Layer 1 is a local stand-in offline; Bedrock adapter not yet run |
| `blueprints/` | RAG (full anatomy); agent, chatbot, batch (seed) | via ch07 lab | n/a | not yet | Canary step is deployer-specific (documented) |
| `agents/` | Registry, budgets, kill switch, approvals, credentials | 9 tests | n/a | not yet | No AgentCore deployment module; readiness item 6 not covered |
| `portal/` | Thin portal | via ch07 lab | n/a | n/a | Backstage track is documented, not packaged |
| `sre/` | RB-1 … RB-5 | game day uses RB-2 | n/a | n/a | — |

## Corrections this repository forced on the book

Building the code found defects in the printed text. They are fixed here and in the
manuscript; readers of earlier drafts should prefer the repository.

1. **Figure 3.1** — `CreateModelInvocationJob` carries no `bedrock:InferenceProfileArn`
   key, so a `Null` test on that key denied every batch job. Batch is now gated by
   principal. A single `Null` block with two tag keys ANDs them (it denied only when
   both tags were missing); each tag is now its own statement. Only platform principals
   may set `approved-model`.
2. **Figure 5.7** — after a `SET LOCAL` ends, `current_setting('app.tenant_id', true)`
   returns `''`, not `NULL`, on the same pooled connection, and `''::uuid` raises. The
   policy now uses `NULLIF(..., '')`.
3. **Figure 6.4** — the query referenced columns that Figure 6.5 does not define, and
   divided by zero for rows without conversations.
