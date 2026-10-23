# AI platform maturity assessment (Appendix B)

Score per capability, never as one grade. Claim a cell only if you can produce its
artifact; a level claimed without evidence is the level below. Panel: one tenant
engineer, one security representative, one FinOps analyst. Disagreements of more than
one level are resolved by looking at the artifact together.

| Capability | Level (0–5) | Evidence (link the artifact) | Repository check |
|---|---|---|---|
| Access (Ch. 4) | | % of AI spend through the gateway; app-held provider keys = 0 | `tests/conformance` green against production |
| Isolation (Ch. 5) | | Leakage test schedule and last result, published | `tests/leakage` in CI and hourly |
| Economics (Ch. 6) | | Drift %, unit costs per outcome, rule versions | `finops/queries/reconciliation.sql` |
| Velocity (Ch. 7) | | Time-to-first-inference distribution; blueprint adoption | `portal` catalog + adoption query |
| Operation (Ch. 8–9) | | Level-3 alarms; drill-measured detection time | `labs/ch09` game-day record |
| Trust (Ch. 10) | | Red-team pass rates per family; audit drill time | `governance` scorecard; audit drill |

Levels: 0–1 Ad hoc · 2 Managed · 3 Defined · 4 Measured · 5 Optimizing (Table B.1).
Publish the result beside last quarter's, with the moves explained.
