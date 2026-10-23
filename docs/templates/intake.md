# Use-case intake (Appendix C.2, Section 10.5)

| Field | Options / format | Feeds |
|---|---|---|
| Use case, owner, tenant | free text + catalog references | Registry (7.3) |
| Data classes touched | org scheme, with per-class examples shown | Matrix enforcement (10.3) |
| Audience | internal / external + human review / external autonomous | Tier rules |
| Decision consequence | informational / operational / consequential | Tier rules |
| Model needs | aliases requested; exotic requirements flagged | Gateway entitlements |
| Legal basis (personal data) | LGPD art. 7 options (art. 11 for sensitive data); balancing test attached if legitimate interest | 10.6 evidence |
| Automated decision? | yes / no — yes means LGPD art. 20 review path | Tier rules |
| Tools requested (agents) | registry entries + risk classes | 12.2 policy |
| → Computed tier | 1 auto-approve / 2 provisional + review SLA / 3 committee + DPIA | `governance/intake/tiering.yaml` |

The computed tier is `platform_governance.classify()` over the answers; the submitter
never chooses it.
