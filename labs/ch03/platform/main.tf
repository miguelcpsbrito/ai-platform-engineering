# labs/ch03/platform — Table 3.5 steps 2–4 in the sandbox account: network, identity,
# the tenants' application profiles, and the gateway stub, plus two lab tenant roles.

terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws     = { source = "hashicorp/aws", version = "~> 6.0" }
    archive = { source = "hashicorp/archive", version = "~> 2.4" }
  }
}

provider "aws" {
  region = var.region
  default_tags {
    tags = { "lab" = "ai-platform-ch03", "cost-center" = "platform-lab" }
  }
}

provider "aws" {
  alias  = "secondary"
  region = var.secondary_region
  default_tags {
    tags = { "lab" = "ai-platform-ch03", "cost-center" = "platform-lab" }
  }
}

variable "region" {
  type    = string
  default = "us-east-1"
}

variable "secondary_region" {
  type    = string
  default = "us-west-2"
}

variable "azs" {
  type    = list(string)
  default = ["us-east-1a", "us-east-1b"]
}

variable "enable_network_firewall" {
  description = "Optional track of Section 3.3 (about $9.50/day per AZ)."
  type        = bool
  default     = false
}

variable "profiles_file" {
  description = "Output of: python -m platform_gateway.profiles --env prod"
  type        = string
  default     = "profiles.json"
}

data "aws_caller_identity" "me" {}

locals {
  account      = data.aws_caller_identity.me.account_id
  me           = "arn:aws:iam::${local.account}:root"
  profiles     = jsondecode(file(var.profiles_file)).profiles
  lab_profiles = [for p in local.profiles : p if contains(["tenant-a", "tenant-b"], p.tenant)]
}

module "identity" {
  source                             = "../../../identity"
  approver_trusted_principal_arns    = [local.me]
  break_glass_trusted_principal_arns = [local.me]
}

module "network" {
  source                  = "../../../network"
  region                  = var.region
  azs                     = var.azs
  enable_network_firewall = var.enable_network_firewall
  platform_role_arns      = [module.identity.gateway_role_arn]
}

module "profiles" {
  source = "../../../gateway/terraform/profiles"
  providers = {
    aws.primary   = aws
    aws.secondary = aws.secondary
  }
  profiles         = local.lab_profiles
  primary_region   = var.region
  secondary_region = var.secondary_region
}

# Lab tenant roles: assumable by you, bounded by the tenant boundary, able to call the
# platform API and nothing model-related directly.
data "aws_iam_policy_document" "lab_tenant_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "AWS"
      identifiers = [local.me]
    }
  }
}

resource "aws_iam_role" "lab_tenant" {
  for_each             = toset(["lab-tenant-a", "lab-tenant-b"])
  name                 = each.value
  assume_role_policy   = data.aws_iam_policy_document.lab_tenant_trust.json
  permissions_boundary = module.identity.tenant_boundary_arn
  max_session_duration = 3600
}

data "aws_iam_policy_document" "lab_tenant" {
  statement {
    actions   = ["lambda:InvokeFunctionUrl", "lambda:InvokeFunction"]
    resources = ["arn:aws:lambda:${var.region}:${local.account}:function:platform-gateway-stub"]
  }
  statement {
    sid       = "ProveTheBoundary"
    actions   = ["bedrock:InvokeModel", "s3:ListAllMyBuckets"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "lab_tenant" {
  for_each = aws_iam_role.lab_tenant
  name     = "lab"
  role     = each.value.id
  policy   = data.aws_iam_policy_document.lab_tenant.json
}

module "gateway" {
  source            = "../../../gateway/terraform/stub"
  package_dir       = "${path.root}/../../../gateway/build/package"
  role_arn          = module.identity.gateway_role_arn
  role_name         = module.identity.gateway_role_name
  vpc_id            = module.network.vpc_id
  vpc_cidr          = module.network.vpc_cidr
  subnet_ids        = module.network.workload_subnet_ids
  profile_map       = module.profiles.profile_map
  invoker_role_arns = [for r in aws_iam_role.lab_tenant : r.arn]
}

output "gateway_url" {
  value = module.gateway.url
}

output "gateway_log_group" {
  value = module.gateway.log_group
}

output "tenant_role_arns" {
  value = { for k, r in aws_iam_role.lab_tenant : k => r.arn }
}

output "vpc_id" {
  value = module.network.vpc_id
}
