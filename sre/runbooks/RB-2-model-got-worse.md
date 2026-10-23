# RB-2: I-2 "the model got worse" with no deploy   Owner: ai-platform SRE   Reviewed: 2026-10

**Trigger** — Regression detector alarm (observability/platform_eval `RegressionDetector`) for an alias, carrying trace IDs; or ≥ 2 tenant reports of quality drops within a day.

| # | Step | Exit criterion |
|---|---|---|
| 1 | Open the regression detector panel for the alias; note first-deviation time and affected suites | Deviation confirmed on ≥ 2 suites or on sampled production scores |
| 2 | Check the gateway config history (`git log gateway/aliases.yaml gateway/env`) and the provider's change notices for that window | Cause classified: our change, provider change, or input drift |
| 3 | If our change: roll back the alias resolution to the previous manifest (`git revert <sha>`, render, deploy) | Scores recover on the next sampling window |
| 4 | If provider change: pin the alias to the last good model version or to the fallback model, if the contract allows (edit `gateway/env/<env>.yaml`) | Scores recover; tenants notified of the pin |
| 5 | If input drift: hand to the tenant with the drift report; no platform rollback | Ticket accepted by the tenant |
| 6 | Re-run every affected tenant suite against the current resolution (`platform-eval <suite> --service <svc>`) | All suites within tolerance |
| 7 | Open a provider case with evaluation diffs and trace exemplars, where relevant | Case number in the incident record |
| 8 | Trigger the postmortem with the detection audit section filled (`docs/templates/postmortem.md`) | Postmortem scheduled |

**Verify** — an evaluation re-run, never a graph alone.

**Communicate** — "Answers on `<alias>` changed in quality from `<time>`; we pinned `<alias>` to the previous behaviour at `<time>`; your suites are being re-run; next update `<time>`."
