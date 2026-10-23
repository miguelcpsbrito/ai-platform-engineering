-- Direct tenant costs from the gateway: tokens × price table, with feature grain.
INSERT INTO allocated_costs
SELECT CAST(substr(ts, 1, 10) AS date) AS usage_date, NULL AS account_id,
       tenant, tenant AS app, feature, alias,
       'inference' AS component, 'unit' AS cost_type, 'gateway' AS source,
       CAST(cost_usd AS decimal(18,6)) AS amount_usd, convo_id,
       '{{rule_version}}' AS rule_version, substr(dt, 1, 7) AS month
FROM   gateway_events
WHERE  substr(dt, 1, 7) = '{{month}}' AND status = 200 AND cost_usd > 0;
