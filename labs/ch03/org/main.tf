# labs/ch03/org — Table 3.5 step 1. Run with management-account (or delegated policy
# administrator) credentials. Creates a lab OU under the root, attaches the three SCPs
# and the tag policy to that OU only, and leaves the rest of the organization alone.

terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 6.0" }
  }
}

provider "aws" {
  region = var.region
}

variable "region" {
  type    = string
  default = "us-east-1"
}

variable "lab_account_id" {
  description = "The sandbox account the lab runs in. It is moved into the lab OU."
  type        = string
}

variable "platform_principal_arns" {
  description = <<-EOT
    Principals allowed to set approved-model tags. Add the role you run Terraform with in
    the sandbox account, e.g. "arn:aws:iam::*:role/aws-reserved/sso.amazonaws.com/*AWSReservedSSO_AdministratorAccess_*".
  EOT
  type        = list(string)
  default     = ["arn:aws:iam::*:role/platform-*"]
}

data "aws_organizations_organization" "this" {}

resource "aws_organizations_organizational_unit" "lab" {
  name      = "ai-platform-lab"
  parent_id = data.aws_organizations_organization.this.roots[0].id
}

module "org" {
  source                  = "../../../org"
  enforced_ou_ids         = [aws_organizations_organizational_unit.lab.id]
  platform_principal_arns = var.platform_principal_arns
  approved_regions        = ["us-east-1", "us-west-2"]
  approved_geographies    = ["us"]
}

output "lab_ou_id" {
  value = aws_organizations_organizational_unit.lab.id
}

output "move_account_command" {
  description = "Moving an account between OUs is deliberate, so the lab prints it instead of doing it."
  value = join(" ", [
    "aws organizations move-account --account-id", var.lab_account_id,
    "--source-parent-id <current parent>",
    "--destination-parent-id", aws_organizations_organizational_unit.lab.id,
  ])
}
