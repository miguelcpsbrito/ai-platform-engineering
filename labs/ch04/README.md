# Lab ch04 — Prove the anatomy (Section 4.9, Table 4.9)

Four scripted proofs of the gateway's core claims. Time: about 3 hours on AWS, five
minutes locally.

## Local track (no AWS)

```bash
python labs/ch04/prove_local.py          # all four
python labs/ch04/prove_local.py --only 2 # one
```

It starts the reference gateway (`gateway/platform_gateway`) in its own process with
simulated models, and runs:

| Proof | Scenario | Artifact |
|---|---|---|
| 1 Swap without code | change `standard` from model A to B in config, reload | served-by header changes; `app.py` hash unchanged |
| 2 Quota isolation | 10× synthetic load on tenant A from other processes | A gets 429s with a machine-readable cause; B's p95 within 10% |
| 3 Fallback | fault layer fails the primary region | every request succeeds from the secondary; fallback-rate alert |
| 4 Cost per feature | `cost_by_feature.sql` on the metering events | spend per tenant per feature, from gateway events alone |

A note on proof 2: the load generator must not share an interpreter with the system
under test — an early version ran both in one process and measured its own contention.

## AWS track (the proxy on EKS)

1. Apply `gateway/terraform/proxy/cluster` (EKS Auto Mode, Aurora Serverless v2,
   Valkey, Pod Identity) on top of the ch03 estate.
2. Create the database user for IAM authentication:
   `CREATE USER litellm; GRANT rds_iam TO litellm; GRANT ALL ON DATABASE litellm TO litellm;`
3. `make -C gateway render PROFILES=<profile_map.json>` and apply
   `gateway/terraform/proxy/app` with `rendered_config_file=gateway/build/litellm/litellm-config.yaml`.
4. Create one LiteLLM team per tenant from `build/litellm/litellm-teams.json`
   (`POST /team/new`) and a key per team.
5. Run the conformance suite against it:
   `PLATFORM_URL=<internal url> PLATFORM_KEY_A=... PLATFORM_KEY_B=... pytest tests/conformance`.
   Where the proxy's native error shapes differ from the platform contract (the 429
   body of Figure 5.5 is the usual one), the suite fails — that is the tripwire of
   Section 4.7 working, and the fix is a thin adapter, not a change to applications.

Cost: [CURRENT.md](CURRENT.md). Teardown: `terraform destroy` on `app`, then `cluster`.
