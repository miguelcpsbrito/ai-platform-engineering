-- FinOps panel: the month by cost type and source, with drift as its own line.
SELECT month, cost_type, source,
       CASE WHEN feature = 'drift' THEN 'drift' ELSE component END AS component,
       ROUND(SUM(amount_usd), 2) AS cost_usd
FROM   finops.allocated_costs
GROUP  BY 1, 2, 3, 4
ORDER  BY 1, cost_usd DESC;
