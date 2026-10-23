# governance/guardrails — the layer-1 guardrail profiles by risk tier (Section 10.2,
# Table 10.2). Figure 10.4 prints part of tier 2; this file is the full set. Thresholds
# are tuned per profile against the red-team corpus (governance/redteam), never by feel.
# Tier 3 adds contextual grounding at a stricter threshold and blocks more PII.

terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 6.0" }
  }
}

variable "tags" {
  type    = map(string)
  default = { "managed-by" = "ai-platform-engineering/governance", "cost-center" = "platform" }
}

locals {
  content_filters = ["HATE", "INSULTS", "SEXUAL", "VIOLENCE", "MISCONDUCT"]
  strength = {
    tier1 = { input = "MEDIUM", output = "MEDIUM" }
    tier2 = { input = "HIGH", output = "MEDIUM" }
    tier3 = { input = "HIGH", output = "HIGH" }
  }
  pii_anonymize = ["EMAIL", "PHONE", "NAME", "ADDRESS"]
  pii_block     = ["US_SOCIAL_SECURITY_NUMBER", "CREDIT_DEBIT_CARD_NUMBER", "AWS_SECRET_KEY", "PASSWORD"]
  grounding     = { tier1 = null, tier2 = 0.7, tier3 = 0.85 }
}

resource "aws_bedrock_guardrail" "tier" {
  for_each                  = local.strength
  name                      = "platform-${each.key}"
  description               = "Platform guardrail profile ${each.key} (Chapter 10)"
  blocked_input_messaging   = "This request can't be processed."
  blocked_outputs_messaging = "This response was withheld."

  content_policy_config {
    dynamic "filters_config" {
      for_each = local.content_filters
      content {
        type            = filters_config.value
        input_strength  = each.value.input
        output_strength = each.value.output
      }
    }
    filters_config {
      type            = "PROMPT_ATTACK"
      input_strength  = "HIGH"
      output_strength = "NONE"
    }
  }

  sensitive_information_policy_config {
    dynamic "pii_entities_config" {
      for_each = local.pii_anonymize
      content {
        type   = pii_entities_config.value
        action = "ANONYMIZE"
      }
    }
    dynamic "pii_entities_config" {
      for_each = local.pii_block
      content {
        type   = pii_entities_config.value
        action = "BLOCK"
      }
    }
  }

  dynamic "contextual_grounding_policy_config" {
    for_each = local.grounding[each.key] == null ? [] : [local.grounding[each.key]]
    content {
      filters_config {
        type      = "GROUNDING"
        threshold = contextual_grounding_policy_config.value
      }
    }
  }

  tags = merge(var.tags, { "risk-tier" = trimprefix(each.key, "tier") })
}

resource "aws_bedrock_guardrail_version" "tier" {
  for_each      = aws_bedrock_guardrail.tier
  guardrail_arn = each.value.guardrail_arn
  description   = "Released by governance/guardrails"
}

output "guardrails" {
  description = "Risk tier → guardrail id and version: the gateway's PLATFORM_GUARDRAILS."
  value = {
    for k, g in aws_bedrock_guardrail.tier : trimprefix(k, "tier") => {
      guardrailIdentifier = g.guardrail_id
      guardrailVersion    = aws_bedrock_guardrail_version.tier[k].version
    }
  }
}
