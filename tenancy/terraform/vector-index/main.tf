# tenancy/terraform/vector-index — an OpenSearch Serverless vector collection for the
# Chapter 5 lab and for level-1/level-2 tenants (shared or dedicated index). Network
# access is VPC-only through an AOSS VPC endpoint; data access is granted per role.

terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 6.0" }
  }
}

variable "name" {
  description = "Collection name: 3–28 lowercase characters."
  type        = string
  default     = "platform-chunks"
}
variable "vpc_id" {
  type = string
}
variable "subnet_ids" {
  type = list(string)
}
variable "security_group_ids" {
  type = list(string)
}
variable "reader_role_arns" {
  description = "Roles that query (the platform retrieval library's callers)."
  type        = list(string)
}
variable "writer_role_arns" {
  description = "Roles that ingest (blueprint ingestion jobs)."
  type        = list(string)
}
variable "tags" {
  type    = map(string)
  default = { "managed-by" = "ai-platform-engineering/tenancy" }
}

resource "aws_opensearchserverless_vpc_endpoint" "this" {
  name               = "${var.name}-vpce"
  vpc_id             = var.vpc_id
  subnet_ids         = var.subnet_ids
  security_group_ids = var.security_group_ids
}

resource "aws_opensearchserverless_security_policy" "encryption" {
  name = "${var.name}-enc"
  type = "encryption"
  policy = jsonencode({
    Rules       = [{ ResourceType = "collection", Resource = ["collection/${var.name}"] }]
    AWSOwnedKey = true
  })
}

resource "aws_opensearchserverless_security_policy" "network" {
  name = "${var.name}-net"
  type = "network"
  policy = jsonencode([{
    Rules = [
      { ResourceType = "collection", Resource = ["collection/${var.name}"] },
      { ResourceType = "dashboard", Resource = ["collection/${var.name}"] },
    ]
    AllowFromPublic = false
    SourceVPCEs     = [aws_opensearchserverless_vpc_endpoint.this.id]
  }])
}

resource "aws_opensearchserverless_access_policy" "data" {
  name = "${var.name}-data"
  type = "data"
  policy = jsonencode([
    {
      Rules = [{ ResourceType = "index", Resource = ["index/${var.name}/*"],
      Permission = ["aoss:ReadDocument", "aoss:DescribeIndex"] }]
      Principal = var.reader_role_arns
    },
    {
      Rules = [{ ResourceType = "index", Resource = ["index/${var.name}/*"],
        Permission = ["aoss:CreateIndex", "aoss:UpdateIndex", "aoss:DescribeIndex",
      "aoss:ReadDocument", "aoss:WriteDocument"] }]
      Principal = var.writer_role_arns
    },
  ])
}

resource "aws_opensearchserverless_collection" "this" {
  name             = var.name
  type             = "VECTORSEARCH"
  standby_replicas = "DISABLED" # lab cost; ENABLED in production
  tags             = var.tags
  depends_on = [aws_opensearchserverless_security_policy.encryption,
  aws_opensearchserverless_security_policy.network]
}

output "endpoint" {
  value = aws_opensearchserverless_collection.this.collection_endpoint
}
