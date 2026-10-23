# Model onboarding record (Appendix C.6, Section 4.8)

| Field | Content |
|---|---|
| Model and version | Provider, exact model identifier, regions, inference profiles |
| Terms review | Terms document and date; training on inputs; retention; sub-processors |
| Data classes allowed | From the data-class × model-class matrix (`gateway/contracts`) |
| Price entry | Input, output, cache, batch prices; cost band per alias (`gateway/prices.yaml`) |
| Evaluation | Scorecard per registered suite; worst-suite result |
| Guardrail compatibility | Red-team pass rates with the target profiles (`governance/redteam`) |
| Quotas | Current quotas per region; increase requests filed |
| Decision | Approved for aliases [...], tiers [...]; reviewer names; date |

Every new model version gets a new record; a version is never onboarded under its
predecessor's terms review.
