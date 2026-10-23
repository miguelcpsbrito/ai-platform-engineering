# Agent readiness (Section 12.4, Table 12.4)

All six must hold before the first consequential-class agent ships. Most estates meet
the first two quickly and the sixth last. Attach the evidence; a box without evidence
is unchecked.

| # | Precondition | Evidence | In this repository |
|---|---|---|---|
| 1 | Tools the agent needs are registered with owners and risk classes | Registry entries; contract tests passing | `agents/registry/tools.yaml`, `agents/tests` |
| 2 | Agent identity is a dedicated role with task-scoped sessions and delegation tags | Session policy; CloudTrail showing tags | `agents/platform_agents/credentials.py` |
| 3 | Consequential actions require approval rendered from structured arguments | Approval channel test; signed approvals | `ApprovalService` and its tests |
| 4 | Step and spend budgets per task, enforced at the gateway and runtime | Budget-exhaustion drill result | `labs/ch12/drill_local.py` output |
| 5 | Kill switches per agent and per tenant, drilled | Game-day record | `labs/ch12/drill_local.py` act 3 |
| 6 | Outcome-based evaluation in a simulation environment, including adversarial tasks | Suite results; unsafe-attempt count of zero | not in this release — see STATUS.md |

Sign-off: platform owner ______  security ______  tenant owner ______  date ______
