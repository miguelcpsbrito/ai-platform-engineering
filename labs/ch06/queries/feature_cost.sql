-- The CFO’s question as SQL (labs/ch06/queries/feature_cost.sql)
SELECT feature,
       SUM(amount_usd)                          AS cost_usd,
       SUM(amount_usd) / NULLIF(COUNT(DISTINCT convo_id), 0)
         AS cost_per_conversation
FROM   finops.allocated_costs
WHERE  month = '2026-05' AND tenant = 'support-chatbot'
GROUP  BY feature ORDER BY cost_usd DESC;
-- runs in seconds; three weeks of archaeology became a WHERE
