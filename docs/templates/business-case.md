# Business case — <platform or capability>         Owner: <name>   Date: <date>

## 1. Cost of the status quo (Section 1.4, Table 1.3)
| Category | Method | Our inputs | Estimate / year |
|---|---|---|---|
| Rework | engineer-weeks of duplicated plumbing × loaded weekly cost | | |
| Lost leverage | fragmented spend × consolidated-commitment discount | | |
| Audit readiness | person-weeks per "where does data meet models" × requests / year | | |
| Data exposure | **not priced** — state the incidents and the obligations they triggered | | — |

## 2. What the platform measurably changes (Chapter 11)
| Board metric (definitions: Section 11.4) | Today | Target in 12 months | How it is measured |
|---|---|---|---|
| Adoption (governed share of AI spend) | | | reconciliation of CUR AI spend vs gateway spend |
| Time to first governed inference (p50 / p90) | | | template run → first gateway call |
| Cost per application (median, top decile) | | | `finops.allocated_costs` |
| Tickets and toil avoided | | | ticket system + team time tracking |
| Use cases reaching production per quarter | | | intake records |

## 3. Cost of the platform
Team (FTE × loaded cost), platform infrastructure (Table 3.6 shape: about 10–12% of AI
spend at Atlas's scale), and the one-off build. Symbolic numbers dated; say which.

## 4. Decision and reversal
The decision in one sentence; the signal that would reopen it (the ADR's Reversal).
