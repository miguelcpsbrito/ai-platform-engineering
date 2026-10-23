-- finops/queries/reconciliation.sql — gateway-metered spend vs CUR actuals, explained in
-- the three legitimate buckets of Section 6.2. Placeholders are filled by finops/lib/pipeline.py.
WITH cur_inv AS (
  SELECT tag_tenant AS tenant, SUM(cost_usd) AS cur_usd
  FROM   cur_normalized
  WHERE  month = '{{month}}' AND service = '{{bedrock_service}}' AND ({{invocation_predicate}})
  GROUP  BY tag_tenant
), gw AS (
  SELECT tenant, SUM(cost_usd) AS gw_usd
  FROM   gateway_events
  WHERE  substr(dt, 1, 7) = '{{month}}' AND status = 200
  GROUP  BY tenant
), cap AS (
  SELECT SUM(cost_usd) AS v FROM cur_normalized
  WHERE  month = '{{month}}' AND service = '{{bedrock_service}}' AND ({{provisioned_predicate}})
)
SELECT 'price_table_drift' AS bucket,
       ROUND(SUM(c.cur_usd - COALESCE(g.gw_usd, 0)), 2) AS amount_usd,
       'fix the price table (gateway/prices.yaml)' AS action
FROM   cur_inv c LEFT JOIN gw g ON c.tenant = g.tenant
WHERE  c.tenant IS NOT NULL
UNION ALL
SELECT 'untagged_or_ungoverned', ROUND(COALESCE(SUM(cur_usd), 0), 2),
       'find the caller: usage without an application profile is shadow AI'
FROM   cur_inv WHERE tenant IS NULL
UNION ALL
SELECT 'capacity_shaped', ROUND(COALESCE(v, 0), 2),
       'allocated by rule 03 (idle bar), never metered by the gateway'
FROM   cap;
