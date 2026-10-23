-- Direct tenant costs the gateway cannot see: tenant-tagged CUR lines outside Bedrock
-- invocation (dedicated indexes, knowledge bases, storage).
INSERT INTO allocated_costs
SELECT usage_date, account_id, tag_tenant AS tenant, tag_tenant AS app,
       COALESCE(tag_feature, 'shared-infra') AS feature, NULL AS alias,
       CASE WHEN service IN ('AmazonOpenSearchService', 'AmazonOpenSearchServerless') THEN 'vector'
            ELSE 'satellite' END AS component,
       'satellite' AS cost_type, 'cur' AS source,
       CAST(cost_usd AS decimal(18,6)), NULL AS convo_id,
       '{{rule_version}}', month
FROM   cur_normalized
WHERE  month = '{{month}}'
  AND  tag_tenant IS NOT NULL
  AND  COALESCE(tag_cost_center, '') <> '{{platform_cost_center}}'
  AND  NOT (service = '{{bedrock_service}}' AND ({{invocation_predicate}} OR {{provisioned_predicate}}));
