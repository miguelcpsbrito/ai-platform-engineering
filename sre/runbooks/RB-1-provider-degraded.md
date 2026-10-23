# RB-1: I-1 provider degraded or out            Owner: ai-platform SRE   Reviewed: 2026-10

**Trigger** — `fallback_rate{alias} > 5% for 5m` or `upstream_5xx{region} > 2%`; Bedrock TimeToFirstToken p99 over the alias contract.

**Classify** — (1) Gateway dashboard → fallback rate by region and model: one region or all? (2) AWS Health for Bedrock in the region. (3) `x-platform-region` in recent traces: is the secondary serving? Confirmed I-1 when errors concentrate on one provider/region and the fallback absorbs them.

**Decide** — Fallback serving and error rate < 1%: monitor, communicate. Fallback saturating (429s from secondary, latency over SLO): go to Act 2. Cross-model fallback in use: state the behaviour change to tenants (Section 9.3).

**Act**
1. Nothing — the fallback chain is the mitigation. Confirm it in traces.
2. Shift the primary for the alias: edit `gateway/env/<env>.yaml` so the secondary region is primary, `make -C gateway render`, deploy through the pipeline. Rollback: revert the commit.
3. If both regions degrade: enable the degradation ladder (`cheaper_alias` for opted-in tenants is automatic; `queue` and `shed` per tenant record).

**Verify** — Error rate under SLO for 15 minutes; fallback rate falling; for cross-model fallback, an evaluation re-run on affected suites.

**Communicate** — Tenant channel every 30 minutes: affected aliases/regions, what users see, whether answers may differ (cross-model), next update time.

**Close** — Postmortem for S1/S2. Attach: fallback timeline, error budget burn attributed `external`.
