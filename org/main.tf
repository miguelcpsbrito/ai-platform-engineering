# org/ — OUs, the three AI SCPs, and the cost-tag policy (Section 3.1, Figures 3.1 and 3.2).
# Apply from the organization's management account (or a delegated policy administrator).

data "aws_organizations_organization" "this" {}

locals {
  root      = data.aws_organizations_organization.this.roots[0].id
  parent_id = coalesce(var.parent_ou_id, local.root)

  scp_vars = {
    platform_principal_arns       = var.platform_principal_arns
    invoke_exempt_principal_arns  = var.invoke_exempt_principal_arns
    approved_regions              = var.approved_regions
    approved_profile_arn_patterns = local.approved_profile_arn_patterns
    break_glass_principal_arns    = var.break_glass_principal_arns
  }

  # Cross-region inference carve-out: geographic system profiles and application
  # profiles homed in an approved region. global.* profiles are never allowed.
  approved_profile_arn_patterns = concat(
    [for g in var.approved_geographies : "arn:aws:bedrock:*:*:inference-profile/${g}.*"],
    [for r in var.approved_regions : "arn:aws:bedrock:${r}:*:application-inference-profile/*"],
  )

  # Keyed by position, not by OU ID, so OUs created in the same apply (whose IDs are
  # unknown at plan time) can be targets.
  attachments = {
    for pair in setproduct(keys(local.policies), range(length(var.enforced_ou_ids))) :
    "${pair[0]}:${pair[1]}" => { policy = pair[0], target = var.enforced_ou_ids[pair[1]] }
  }

  # Policies are minified before upload; SCPs are limited to 5,120 characters.
  policies = {
    ai-model-allowlist = templatefile("${path.module}/scps/model-allowlist.json.tftpl", local.scp_vars)
    ai-region-restrict = templatefile("${path.module}/scps/region-restriction.json.tftpl", local.scp_vars)
    ai-mandatory-tags  = templatefile("${path.module}/scps/mandatory-tags.json.tftpl", local.scp_vars)
  }
}

resource "aws_organizations_organizational_unit" "ou" {
  for_each  = var.create_ous ? toset(var.ou_names) : toset([])
  name      = each.value
  parent_id = local.parent_id
  tags      = var.tags
}

resource "aws_organizations_policy" "scp" {
  for_each    = local.policies
  name        = each.key
  description = "AI platform guardrail (Section 3.1) — managed by org/"
  type        = "SERVICE_CONTROL_POLICY"
  content     = jsonencode(jsondecode(each.value))
  tags        = var.tags
}

# SCPs attach to OUs, never to accounts: a vended account inherits every guardrail.
# Attach to the test OU first (Section 3.1); widen enforced_ou_ids after the suite passes.
resource "aws_organizations_policy_attachment" "scp" {
  for_each  = local.attachments # policy × OU, test OU first
  policy_id = aws_organizations_policy.scp[each.value.policy].id
  target_id = each.value.target
}

resource "aws_organizations_policy" "ai_tags" {
  name        = "ai-cost-tags"
  description = "Standardizes the cost-allocation keys Chapter 6 depends on"
  type        = "TAG_POLICY"
  content     = file("${path.module}/tag-policies/ai-cost-tags.json")
  tags        = var.tags
}

resource "aws_organizations_policy_attachment" "ai_tags" {
  for_each  = { for i, id in var.enforced_ou_ids : tostring(i) => id }
  policy_id = aws_organizations_policy.ai_tags.id
  target_id = each.value
}
