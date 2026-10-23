# finops/ — cost as an engineering property (Chapter 6)

| Path | What |
|---|---|
| `athena/` | `allocated_costs` (Figure 6.5), `gateway_events` (Firehose JSON, partition projection), `cur_normalized` over CUR 2.0 |
| `allocation/rules.yaml` | Rule version, 70% idle bar, $400 shared floor, CUR usage-type patterns |
| `allocation/0*.sql` | Direct tokens → direct satellite → reserved capacity at the idle bar → shared pool → drift |
| `queries/reconciliation.sql` | Gateway vs CUR in three buckets: price-table drift, untagged usage, capacity-shaped |
| `lib/pipeline.py` | Runs the steps on DuckDB or Athena |
| `lib/anomaly.py` | Hourly burn per tenant and feature vs a robust baseline; the page names tenant, feature and burn |
| `lib/weekly_message.py` | Figure 6.6 |
| `cost-model/model_plane_tco.py` | Figure 3.3's arithmetic as a calculator |
| `terraform/` | CUR 2.0 via Data Exports, metering Firehose, Glue database, Athena workgroup |

The SQL is portable between Athena (Trino) and DuckDB; the tests run every step on a
synthetic month and check that allocated totals tie out to the CUR.
