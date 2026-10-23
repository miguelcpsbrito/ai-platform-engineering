-- Reserved capacity (provisioned throughput floors): the tenant pays
-- cost × max(utilization, idle_bar); the rest is idle above the bar, held centrally.
INSERT INTO allocated_costs
SELECT c.usage_date, c.account_id, u.tenant, u.tenant, 'reserved-floor', NULL,
       'inference', 'capacity', 'allocation',
       CAST(c.cost_usd * LEAST(1.0, GREATEST(u.utilization, {{idle_bar}})) AS decimal(18,6)),
       NULL, '{{rule_version}}', c.month
FROM   cur_normalized c JOIN capacity_utilization u
       ON c.resource_id = u.resource_id AND c.month = u.month
WHERE  c.month = '{{month}}' AND c.service = '{{bedrock_service}}' AND ({{provisioned_predicate_c}})
UNION ALL
SELECT c.usage_date, c.account_id, '_platform_idle', '_platform', 'idle-above-bar', NULL,
       'inference', 'capacity', 'allocation',
       CAST(c.cost_usd * (1.0 - LEAST(1.0, GREATEST(u.utilization, {{idle_bar}}))) AS decimal(18,6)),
       NULL, '{{rule_version}}', c.month
FROM   cur_normalized c JOIN capacity_utilization u
       ON c.resource_id = u.resource_id AND c.month = u.month
WHERE  c.month = '{{month}}' AND c.service = '{{bedrock_service}}' AND ({{provisioned_predicate_c}});
