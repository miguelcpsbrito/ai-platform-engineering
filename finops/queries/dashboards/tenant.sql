-- Tenant panel: one tenant's features with cost per conversation (the unit economics).
SELECT feature, ROUND(SUM(amount_usd), 2) AS cost_usd,
       ROUND(SUM(amount_usd) / NULLIF(COUNT(DISTINCT convo_id), 0), 4) AS cost_per_conversation
FROM   finops.allocated_costs
WHERE  month = '{{month}}' AND tenant = '{{tenant}}'
GROUP  BY feature
ORDER  BY cost_usd DESC;
