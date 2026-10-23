-- labs/ch04/cost_by_feature.sql — yesterday's spend per tenant per feature, from gateway
-- metering events alone (Table 4.9, proof 4). Runs unchanged on Athena (table
-- finops.gateway_events, partitioned by dt) and on DuckDB (the local lab creates the same view).
-- {{day}} is replaced by the runner with an ISO date, e.g. 2026-10-22.
SELECT tenant,
       feature,
       COUNT(*)                         AS calls,
       SUM(tokens_in + tokens_out)      AS tokens,
       ROUND(SUM(cost_usd), 6)          AS cost_usd,
       ROUND(AVG(cost_usd), 6)          AS cost_per_call,
       SUM(CASE WHEN fallback THEN 1 ELSE 0 END) AS fallback_calls
FROM   gateway_events
WHERE  dt = '{{day}}'
  AND  status = 200
GROUP  BY tenant, feature
ORDER  BY cost_usd DESC;
