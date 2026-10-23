-- finops/athena/allocated_costs.sql — the shared schema between every source and every
-- dashboard (Section 6.5, Figure 6.5). rule_version makes every number reproducible.
CREATE EXTERNAL TABLE finops.allocated_costs (
  usage_date     date,
  account_id     string,
  tenant         string,
  app            string,
  feature        string,
  alias          string,
  component      string,   -- inference, vector, satellite, ...
  cost_type      string,   -- unit | capacity | satellite
  source         string,   -- gateway | cur | allocation
  amount_usd     decimal(18,6),
  convo_id       string,
  rule_version   string
)
PARTITIONED BY (month string)
STORED AS PARQUET
LOCATION 's3://finops-curated/allocated_costs/';
