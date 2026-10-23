-- finops/queries/lever_ranking.sql — which optimization lever first, per feature, from
-- the estate's own bill (Section 6.4, Table 6.2). Not clever on purpose: shares from
-- gateway events, savings from the playbook's mid-range figures. Placeholders are filled
-- by finops/lib/pipeline.py (prices from gateway/prices.yaml, rules from rules.yaml).
WITH prices (model, p_in, p_out) AS (VALUES {{model_prices_values}}),
f AS (
  SELECT e.tenant, e.feature,
         SUM(e.cost_usd)                                             AS cost,
         SUM(e.tokens_out * p.p_out / 1e6) / NULLIF(SUM(e.cost_usd), 0) AS output_share,
         SUM(e.tokens_in * p.p_in / 1e6) / NULLIF(SUM(e.cost_usd), 0)   AS input_share,
         SUM(CASE WHEN e.alias = 'premium' THEN e.cost_usd ELSE 0 END)
           / NULLIF(SUM(e.cost_usd), 0)                              AS premium_share,
         AVG(e.tokens_in)                                            AS avg_in,
         STDDEV_SAMP(e.tokens_in) / NULLIF(AVG(e.tokens_in), 0)      AS in_cv,
         AVG(e.tokens_out)                                           AS avg_out
  FROM   gateway_events e JOIN prices p ON e.model = p.model
  WHERE  substr(e.dt, 1, 7) = '{{month}}' AND e.status = 200
  GROUP  BY e.tenant, e.feature
), levers AS (
  SELECT tenant, feature, cost, 'output_discipline' AS lever,
         cost * output_share * 0.20 AS est_saving_usd                 -- 10–30% of output tokens
  FROM f
  UNION ALL
  SELECT tenant, feature, cost, 'prompt_caching',
         CASE WHEN avg_in >= 1500 AND in_cv < 0.3                      -- long, stable prefixes
              THEN cost * input_share * 0.8 * 0.9 ELSE 0 END           -- 80% hit, reads ~90% off
  FROM f
  UNION ALL
  SELECT tenant, feature, cost, 'batch',
         CASE WHEN feature IN ({{latency_tolerant_features}}) THEN cost * 0.5 ELSE 0 END
  FROM f
  UNION ALL
  SELECT tenant, feature, cost, 'model_per_task',
         cost * premium_share * 0.8                                    -- premium ≈ 5x standard
  FROM f
)
SELECT tenant, feature, ROUND(cost, 2) AS cost_usd, lever, ROUND(est_saving_usd, 2) AS est_saving_usd,
       RANK() OVER (PARTITION BY tenant, feature ORDER BY est_saving_usd DESC) AS lever_rank
FROM   levers
WHERE  est_saving_usd > 0
ORDER  BY cost_usd DESC, lever_rank;
