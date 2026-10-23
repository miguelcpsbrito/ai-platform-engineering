-- finops/athena/cur_normalized.sql — CUR 2.0 (AWS Data Exports) reduced to the columns
-- allocation needs (Section 6.2). Tags appear in resource_tags with the "user_" prefix.
-- The Bedrock usage_type distinguishes input/output tokens, cache, provisioned
-- throughput hours, batch and guardrail text units.
CREATE OR REPLACE VIEW finops.cur_normalized AS
SELECT CAST(line_item_usage_start_date AS date)          AS usage_date,
       line_item_usage_account_id                         AS account_id,
       line_item_product_code                             AS service,
       line_item_usage_type                               AS usage_type,
       line_item_resource_id                              AS resource_id,
       element_at(resource_tags, 'user_tenant')           AS tag_tenant,
       element_at(resource_tags, 'user_cost-center')      AS tag_cost_center,
       element_at(resource_tags, 'user_feature')          AS tag_feature,
       line_item_unblended_cost                           AS cost_usd,
       billing_period                                     AS month
FROM   finops.cur2
WHERE  line_item_line_item_type IN ('Usage', 'DiscountedUsage', 'SavingsPlanCoveredUsage');
