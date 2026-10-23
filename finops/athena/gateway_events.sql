-- finops/athena/gateway_events.sql — gateway metering events as delivered by Firehose
-- (gateway/platform_gateway/metering.py is the producer; the field list is the contract).
-- Partition projection on dt keeps the table maintenance-free.
CREATE EXTERNAL TABLE finops.gateway_events (
  ts             string,
  trace_id       string,
  tenant         string,
  feature        string,
  convo_id       string,
  alias          string,
  provider       string,
  model          string,
  region         string,
  tier           string,
  status         int,
  fallback       boolean,
  attempts       int,
  cache_hit      boolean,
  tokens_in      bigint,
  tokens_out     bigint,
  tokens_cached  bigint,
  cost_usd       double,
  latency_ms     double,
  config_version string,
  environment    string
)
PARTITIONED BY (dt string)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
LOCATION 's3://finops-raw/gateway-events/'
TBLPROPERTIES (
  'projection.enabled' = 'true',
  'projection.dt.type' = 'date',
  'projection.dt.format' = 'yyyy-MM-dd',
  'projection.dt.range' = '2026-01-01,NOW',
  'storage.location.template' = 's3://finops-raw/gateway-events/dt=${dt}/'
);
