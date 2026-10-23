# RB-4: I-4 guardrail incident                      Owner: ai-platform security   Reviewed: 2026-10

**Trigger** — A red-team regression in the scheduled run; a guardrail intervention spike; or a report of harmful or disclosed content.

**Classify** — (1) Which layer let it through (scorecard per layer). (2) Data class of the affected tenant and whether personal data left the organization (audit records for the window: `governance` audit drill). (3) Scope: one tenant, one alias, or the profile.

**Decide** — Personal data possibly disclosed: notify the DPO and legal now — notification decisions are theirs (Section 10.6). Profile gap: tighten layer 1 or add a layer-2 rule. Single-service output issue: layer 3 contract fix in the service.

**Act**
1. Add the case to `governance/redteam/corpus.yaml` (it must fail before the fix).
2. Fix at the right layer; release a new guardrail version via `governance/guardrails`.
3. Re-run the red-team suite; the new case passes and no family regresses.

**Verify** — Scorecard per family at or above the previous release; false-positive rate on benign cases unchanged.

**Communicate** — Security channel and affected tenants; facts only: data classes, tenants, window, whether data left the organization.

**Close** — Postmortem always. Attach: audit records for the window, scorecards before and after.
