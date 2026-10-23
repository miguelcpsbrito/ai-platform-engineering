-- Shared platform costs: every tenant pays a floor, the remainder splits by share of
-- direct cost (Section 6.3, Atlas year two).
INSERT INTO allocated_costs
WITH shared AS (
  SELECT SUM(cost_usd) AS pool FROM cur_normalized
  WHERE  month = '{{month}}' AND tag_cost_center = '{{platform_cost_center}}'
), direct AS (
  SELECT tenant, SUM(amount_usd) AS d FROM allocated_costs
  WHERE  month = '{{month}}' AND rule_version = '{{rule_version}}'
    AND  cost_type IN ('unit', 'satellite', 'capacity') AND tenant NOT LIKE '\_%' ESCAPE '\'
  GROUP  BY tenant
), n AS (SELECT COUNT(*) AS tenants, SUM(d) AS total FROM direct)
SELECT CAST('{{month}}-01' AS date), NULL, direct.tenant, direct.tenant, 'platform-share', NULL,
       'shared', 'allocation', 'allocation',
       CAST(LEAST(shared.pool / n.tenants, {{shared_floor_usd}})
            + GREATEST(shared.pool - {{shared_floor_usd}} * n.tenants, 0) * direct.d / n.total
            AS decimal(18,6)),
       NULL, '{{rule_version}}', '{{month}}'
FROM   direct CROSS JOIN shared CROSS JOIN n
WHERE  shared.pool IS NOT NULL;
