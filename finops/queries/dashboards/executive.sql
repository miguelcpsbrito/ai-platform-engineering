-- Executive panel: allocated AI cost per tenant per month, with the platform's own share.
SELECT month, tenant, ROUND(SUM(amount_usd), 2) AS cost_usd
FROM   finops.allocated_costs
GROUP  BY month, tenant
ORDER  BY month, cost_usd DESC;
