# identity/ — roles, permission boundaries, Identity Center, Pod Identity, break-glass
# (Section 3.4). No static keys anywhere: humans federate, workloads assume roles.

data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
  partition  = data.aws_partition.current.partition
}

# --- Permission boundary every tenant and blueprint role is created under ----------

resource "aws_iam_policy" "tenant_boundary" {
  name        = "${var.prefix}-tenant-boundary"
  description = "Ceiling for tenant workload roles (Section 3.4)"
  policy      = file("${path.module}/policies/tenant-boundary.json")
  tags        = var.tags
}

# --- The gateway's workload role ------------------------------------------------------

# EKS Pod Identity for the proxy (4.5); Lambda for the minimal platform's stub (3.6).
data "aws_iam_policy_document" "gateway_trust" {
  statement {
    actions = ["sts:AssumeRole", "sts:TagSession"]
    principals {
      type        = "Service"
      identifiers = ["pods.eks.amazonaws.com", "lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "gateway" {
  name                 = "${var.prefix}-gateway"
  description          = "AI gateway workload role — the one principal that invokes models (4.5)"
  assume_role_policy   = data.aws_iam_policy_document.gateway_trust.json
  max_session_duration = 3600
  tags                 = var.tags
}

data "aws_iam_policy_document" "gateway" {
  statement {
    sid     = "InvokeThroughApplicationProfiles"
    actions = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]
    resources = [
      "arn:${local.partition}:bedrock:*:${local.account_id}:application-inference-profile/*",
      "arn:${local.partition}:bedrock:*:${local.account_id}:inference-profile/*",
      "arn:${local.partition}:bedrock:*::foundation-model/*",
    ]
  }
  statement {
    sid       = "ApplyPlatformGuardrails"
    actions   = ["bedrock:ApplyGuardrail"]
    resources = ["arn:${local.partition}:bedrock:*:${local.account_id}:guardrail/*"]
  }
  statement {
    sid       = "ReadProviderSecrets"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = ["arn:${local.partition}:secretsmanager:*:${local.account_id}:secret:${var.prefix}/gateway/*"]
  }
  statement {
    sid       = "ConnectToGatewayStateWithIAM"
    actions   = ["rds-db:connect"]
    resources = ["arn:${local.partition}:rds-db:*:${local.account_id}:dbuser:*/litellm"]
  }
  statement {
    sid       = "EmitMetering"
    actions   = ["firehose:PutRecord", "firehose:PutRecordBatch"]
    resources = ["arn:${local.partition}:firehose:*:${local.account_id}:deliverystream/${var.prefix}-metering*"]
  }
}

resource "aws_iam_role_policy" "gateway" {
  name   = "gateway"
  role   = aws_iam_role.gateway.id
  policy = data.aws_iam_policy_document.gateway.json
}

# --- The model approver: the only principal that sets approved-model tags (10.4) ----

data "aws_iam_policy_document" "approver_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "AWS"
      identifiers = var.approver_trusted_principal_arns
    }
    condition {
      test     = "Bool"
      variable = "aws:MultiFactorAuthPresent"
      values   = ["true"]
    }
  }
}

resource "aws_iam_role" "model_approver" {
  name                 = "${var.prefix}-model-approver"
  assume_role_policy   = data.aws_iam_policy_document.approver_trust.json
  max_session_duration = 3600
  tags                 = var.tags
}

data "aws_iam_policy_document" "model_approver" {
  statement {
    actions = ["bedrock:CreateInferenceProfile", "bedrock:TagResource",
    "bedrock:GetInferenceProfile", "bedrock:ListInferenceProfiles"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "model_approver" {
  name   = "approve-models"
  role   = aws_iam_role.model_approver.id
  policy = data.aws_iam_policy_document.model_approver.json
}

# --- Break-glass: MFA, one hour, loud ------------------------------------------------

data "aws_iam_policy_document" "break_glass_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "AWS"
      identifiers = var.break_glass_trusted_principal_arns
    }
    condition {
      test     = "Bool"
      variable = "aws:MultiFactorAuthPresent"
      values   = ["true"]
    }
    condition {
      test     = "NumericLessThan"
      variable = "aws:MultiFactorAuthAge"
      values   = ["900"]
    }
  }
}

resource "aws_iam_role" "break_glass" {
  name                 = "break-glass-${var.prefix}"
  assume_role_policy   = data.aws_iam_policy_document.break_glass_trust.json
  max_session_duration = 3600
  tags                 = merge(var.tags, { "alert-on-use" = "true" })
}

resource "aws_iam_role_policy_attachment" "break_glass" {
  role       = aws_iam_role.break_glass.name
  policy_arn = "arn:${local.partition}:iam::aws:policy/AdministratorAccess"
}

# Every break-glass assumption pages someone (Section 3.4).
resource "aws_cloudwatch_event_rule" "break_glass_used" {
  name        = "${var.prefix}-break-glass-used"
  description = "AssumeRole on the break-glass role"
  event_pattern = jsonencode({
    source      = ["aws.sts"]
    detail-type = ["AWS API Call via CloudTrail"]
    detail = {
      eventName         = ["AssumeRole"]
      requestParameters = { roleArn = [aws_iam_role.break_glass.arn] }
    }
  })
  tags = var.tags
}

resource "aws_cloudwatch_event_target" "break_glass_used" {
  count = var.alert_topic_arn == null ? 0 : 1
  rule  = aws_cloudwatch_event_rule.break_glass_used.name
  arn   = var.alert_topic_arn
}
