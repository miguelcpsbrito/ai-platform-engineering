# identity/ — roles, boundaries, no static keys (Section 3.4)

**Proves:** zero static keys; a tenant role cannot reach a model except through the gateway.

- `gateway` role — the one workload principal that invokes models (Pod Identity for the proxy, Lambda for the stub); IAM auth to the gateway's Postgres.
- `policies/tenant-boundary.json` — ceiling for every tenant and blueprint role: no direct model access, no access keys, no identity or egress changes.
- `model-approver` — the only role that sets `approved-model` (MFA).
- `break-glass-*` — MFA, one-hour sessions, an EventBridge rule on every assumption.
- `identity_center.tf` — permission sets for the personas of Section 2.4 (optional).
