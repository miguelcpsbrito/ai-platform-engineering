# tenancy/terraform/registry — the tenant registry table (Table A.2: consumed by finops/
# and governance/). Git holds the records; this table is their deployed projection,
# written by the gateway pipeline on merge, read by allocation and the deletion pipeline.

terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 6.0" }
  }
}

variable "name" {
  type    = string
  default = "platform-tenants"
}
variable "tags" {
  type    = map(string)
  default = { "managed-by" = "ai-platform-engineering/tenancy" }
}

resource "aws_dynamodb_table" "tenants" {
  name                        = var.name
  billing_mode                = "PAY_PER_REQUEST"
  hash_key                    = "tenant"
  deletion_protection_enabled = true

  attribute {
    name = "tenant"
    type = "S"
  }
  attribute {
    name = "id"
    type = "S"
  }

  global_secondary_index {
    name            = "by-id"
    hash_key        = "id"
    projection_type = "ALL"
  }

  point_in_time_recovery {
    enabled = true
  }
  server_side_encryption {
    enabled = true
  }
  tags = var.tags
}

output "table_name" {
  value = aws_dynamodb_table.tenants.name
}
output "table_arn" {
  value = aws_dynamodb_table.tenants.arn
}
