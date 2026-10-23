# RB-3: I-3 cost explosion                         Owner: ai-platform SRE + FinOps   Reviewed: 2026-10

**Trigger** — Spend anomaly page (finops/lib/anomaly.py) naming tenant, feature and hourly burn; or a tenant budget at 100% forecast before mid-month.

**Classify** — (1) The page's top-conversation share: > 50% of calls in one conversation is a retry loop or a runaway agent. (2) Calls per feature vs the 72-hour baseline: traffic growth vs per-call cost growth. (3) For agents: steps per task from trajectory traces.

**Decide** — Retry loop or runaway: Act 1 now, then contact the tenant. Legitimate growth: no action beyond budget conversation. Price-table drift: FinOps fixes `gateway/prices.yaml`.

**Act**
1. Budget kill switch for the tenant's feature or agent (agents: `KillSwitch.pull("agent:<name>")`; gateway: lower the tenant's `tokens_per_minute` in its record — a reviewed one-line PR — and deploy). Rollback: revert.
2. Ask the tenant to fix the client; keep the limit until the fix is deployed.

**Verify** — Hourly burn back within 2× baseline for 2 hours.

**Communicate** — Direct message to the tenant owner with the page, the conversation ID and the limit applied.

**Close** — Postmortem if spend impact > $1,000 or a budget was breached; attach the anomaly page and the hourly burn series.
