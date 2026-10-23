# gateway/terraform/profiles — one application inference profile per tenant × model ×
# region (Section 4.4, Figure 4.5). The tags are what org/'s SCP checks, and the
# copied geographic profile keeps cross-region routing.
#
# Input comes from the gateway's own config, never typed by hand:
#   python -m platform_gateway.profiles --env prod > profiles.auto.tfvars.json
# Apply as a platform principal: the SCP lets only platform-* roles set approved-model.

terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = {
      source                = "hashicorp/aws"
      version               = "~> 6.0"
      configuration_aliases = [aws.primary, aws.secondary]
    }
  }
}

data "aws_caller_identity" "current" {
  provider = aws.primary
}

locals {
  account = data.aws_caller_identity.current.account_id
  by_region = {
    primary   = { for p in var.profiles : p.key => p if p.region == var.primary_region }
    secondary = { for p in var.profiles : p.key => p if p.region == var.secondary_region }
  }
  unplaced = [for p in var.profiles : p.key if !contains([var.primary_region, var.secondary_region], p.region)]
}

resource "aws_bedrock_inference_profile" "primary" {
  provider    = aws.primary
  for_each    = local.by_region.primary
  name        = each.value.name
  description = "Tenant ${each.value.tenant} — ${each.value.model}"
  model_source {
    copy_from = "arn:aws:bedrock:${each.value.region}:${local.account}:inference-profile/${each.value.model}"
  }
  tags = merge(var.tags, {
    "approved-model" = "true"
    "cost-center"    = each.value.cost_center
    "tenant"         = each.value.tenant
  })

  lifecycle {
    precondition {
      condition     = length(local.unplaced) == 0
      error_message = "Profiles requested in regions this module does not manage: ${join(", ", local.unplaced)}"
    }
  }
}

resource "aws_bedrock_inference_profile" "secondary" {
  provider    = aws.secondary
  for_each    = local.by_region.secondary
  name        = each.value.name
  description = "Tenant ${each.value.tenant} — ${each.value.model} (fallback region)"
  model_source {
    copy_from = "arn:aws:bedrock:${each.value.region}:${local.account}:inference-profile/${each.value.model}"
  }
  tags = merge(var.tags, {
    "approved-model" = "true"
    "cost-center"    = each.value.cost_center
    "tenant"         = each.value.tenant
  })
}
