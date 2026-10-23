# tenancy/terraform/baseline — what lands in every vended tenant account before the
# tenant logs in (Section 3.1): a tenant KMS key, a budget wired to the tenant's
# channel, and the tag that ties the account to its tenant record. Network attachment
# and identity roles come from network/ and identity/; Account Factory (AFT) applies
# this module as an account customization.

terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 6.0" }
  }
}

data "aws_caller_identity" "current" {}

resource "aws_kms_key" "tenant" {
  description             = "Tenant ${var.tenant} data key (Chapter 5 placement.kms_key)"
  enable_key_rotation     = true
  deletion_window_in_days = 30
  tags                    = merge(var.tags, { tenant = var.tenant })
}

resource "aws_kms_alias" "tenant" {
  name          = "alias/tenant/${var.tenant}"
  target_key_id = aws_kms_key.tenant.key_id
}

resource "aws_budgets_budget" "tenant" {
  name         = "tenant-${var.tenant}"
  budget_type  = "COST"
  limit_amount = tostring(var.monthly_budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = var.alert_emails
  }
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = var.alert_emails
  }
}
