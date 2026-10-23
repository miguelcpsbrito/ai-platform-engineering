# ${{ values.name }} infrastructure, applied by this repository's own pipeline — the
# portal never holds deploy credentials (Figure 7.3 caption). The workload role is
# created under the tenant permission boundary from identity/.

variable "tenant_boundary_arn" {
  type = string
}

data "aws_iam_policy_document" "trust" {
  statement {
    actions = ["sts:AssumeRole", "sts:TagSession"]
    principals {
      type        = "Service"
      identifiers = ["pods.eks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "workload" {
  name                 = "${{ values.name }}-prod"
  assume_role_policy   = data.aws_iam_policy_document.trust.json
  permissions_boundary = var.tenant_boundary_arn
  tags = {
    tenant          = "${{ values.tenant }}"
    "cost-center"   = "${{ values.tenant }}"
    "risk-tier"     = "${{ values.riskTier }}"
    "ai-blueprint"  = "rag-service@7.2.0"
  }
}
