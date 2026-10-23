# Lab ch06 — Answer the CFO in one query (Section 6.8, Table 6.7)

## Local track (steps 5–8)

```bash
python labs/ch06/run_local.py
```

Generates a simulated week (two tenants, four features, a retry loop hidden in
`refund-flow` on 16 May at 14:00), runs the five allocation steps on DuckDB, answers
`queries/feature_cost.sql` from cold, explains drift in three buckets, and pages on the
retry loop with tenant, feature and hourly burn.

## AWS track (steps 1–4, then the same queries on Athena)

1. Apply `finops/terraform` (Data Exports must be created in us-east-1). First CUR 2.0
   file lands within 24 hours.
2. Set the gateway's `PLATFORM_METERING_SINK=firehose` and
   `PLATFORM_METERING_STREAM=<metering_stream output>`.
3. Create the tables: `finops/athena/*.sql` (replace the bucket names in `LOCATION`
   with the module outputs).
4. Run the allocation: `python finops/lib/pipeline.py --engine athena --month 2026-05`.
   Every row carries `rule_version`; change `finops/allocation/rules.yaml` (the 70% idle
   bar, the $400 floor) and re-run to argue with the defaults.
