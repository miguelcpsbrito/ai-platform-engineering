-- Reconciliation: Bedrock invocation spend in the CUR minus what the gateway metered.
-- The difference is booked to _unallocated so totals tie out to the invoice; the
-- reconciliation report explains it in three buckets (queries/reconciliation.sql).
INSERT INTO allocated_costs
WITH cur AS (
  SELECT SUM(cost_usd) AS v FROM cur_normalized
  WHERE  month = '{{month}}' AND service = '{{bedrock_service}}' AND ({{invocation_predicate}})
), gw AS (
  SELECT SUM(amount_usd) AS v FROM allocated_costs
  WHERE  month = '{{month}}' AND rule_version = '{{rule_version}}' AND source = 'gateway'
)
SELECT CAST('{{month}}-01' AS date), NULL, '_unallocated', '_unallocated', 'drift', NULL,
       'inference', 'allocation', 'allocation',
       CAST(cur.v - COALESCE(gw.v, 0) AS decimal(18,6)), NULL, '{{rule_version}}', '{{month}}'
FROM   cur CROSS JOIN gw
WHERE  cur.v IS NOT NULL;
