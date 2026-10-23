# tests/ — the book's claims, falsifiable (Appendix A.3)

| Suite | Path | In CI | Scheduled (production) |
|---|---|---|---|
| Leakage | `leakage/` | every change to retrieval paths or tenant records | hourly, synthetic tenants |
| Conformance | `conformance/` | every gateway config or image change | daily against production |
| Restore | `restore/` | procedure tested on every change | quarterly per vector engine |
| SCP guardrails | `scp/` (live, `SCP_LIVE=1`) | unit tests in `org/tests` | weekly in the test OU |
| Red team | `governance/tests` + corpus | every guardrail change | daily against production profiles |
| Deletion | `governance/tests` | every change to stores or the pipeline | weekly synthetic subject |

The production schedules are the operator's to wire (EventBridge Scheduler or CI cron
against the live endpoints); the suites take their targets from environment variables.
