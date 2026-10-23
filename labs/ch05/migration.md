# Tenancy migration checklist — full version (Section 5.6, Table 5.8)

Reference case: logical tenant to dedicated account (isolation level 1 → 3). Each phase
has an exit gate; the gates, not the calendar, sequence the move. Record every gate's
evidence in the tenant record's `history` and in the migration ticket.

## 1. Provision
- [ ] Vend the target account (Account Factory) into the Workloads OU; `tenancy/terraform/baseline` lands: KMS key `alias/tenant/<id>`, budget, tags.
- [ ] Network attachment to the hub; DNS Firewall rule group associated.
- [ ] Identity roles created under the tenant boundary.
- **Exit gate:** leakage suite and SCP tests pass against the empty target.

## 2. Replicate
- [ ] Prefer reingesting from source documents (exercises the blueprint, re-encrypts under the new key).
- [ ] Otherwise snapshot + restore with re-encryption under the tenant's key.
- [ ] Corpus counts per source match; spot-check 50 retrievals.
- **Exit gate:** counts match; restore drill retrieval diff is empty (`tests/restore`).

## 3. Shadow
- [ ] Replay or dual-run the tenant's traffic against the new stack.
- [ ] Run the tenant's evaluation suites against both; compare retrieval sets and answer scores.
- **Exit gate:** deltas within agreed thresholds for N consecutive days (default 7).

## 4. Cut over
- [ ] Edit the tenant record's `placement` and append to `history` (one reviewed PR).
- [ ] Deploy the gateway config; applications change nothing.
- **Exit gate:** error rate and latency steady for 24 h; fallback silent.

## 5. Reconcile
- [ ] Move quotas and capacity floors; re-home dashboards.
- [ ] Carry cost lineage: the tenant's allocated-cost trend continues across the move.
- **Exit gate:** the tenant's trend lines are unbroken in the FinOps dashboards.

## 6. Decommission
- [ ] Delete the tenant's rows from the shared index, cache and logs through the deletion pipeline.
- [ ] Attach the completion report to the migration record.
- **Exit gate:** completion report shows zero residue in every store; backup expiry stated.
