# gateway/terraform/proxy/cluster — the infrastructure under the open-source proxy of
# Section 4.5: an EKS Auto Mode cluster in the platform account, Aurora Serverless v2
# (PostgreSQL) for tenant/key/config state, ElastiCache Serverless (Valkey) for shared
# rate-limit counters and the exact cache, and the Pod Identity binding that gives the
# proxy the gateway role. Apply this first; proxy/app installs the proxy onto it.

terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 6.0" }
  }
}

variable "name" {
  type    = string
  default = "platform-gateway"
}
variable "vpc_id" {
  type = string
}
variable "vpc_cidr" {
  type = string
}
variable "subnet_ids" {
  description = "network/ workload subnets, at least two AZs."
  type        = list(string)
}
variable "gateway_role_arn" {
  description = "identity/ gateway role; bound to the proxy's service account by Pod Identity."
  type        = string
}
variable "kubernetes_version" {
  type    = string
  default = "1.33"
}
variable "public_endpoint" {
  description = "Public API endpoint for labs run from a laptop. False in production."
  type        = bool
  default     = true
}
variable "admin_principal_arns" {
  description = "Principals granted cluster admin through access entries."
  type        = list(string)
}
variable "db_min_acu" {
  description = "Aurora Serverless v2 floor. 0 enables auto-pause (lab cost); use >= 0.5 in production."
  type        = number
  default     = 0
}
variable "tags" {
  type    = map(string)
  default = { "managed-by" = "ai-platform-engineering/gateway" }
}

# --- EKS Auto Mode ----------------------------------------------------------------

data "aws_iam_policy_document" "cluster_trust" {
  statement {
    actions = ["sts:AssumeRole", "sts:TagSession"]
    principals {
      type        = "Service"
      identifiers = ["eks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "cluster" {
  name               = "${var.name}-eks-cluster"
  assume_role_policy = data.aws_iam_policy_document.cluster_trust.json
  tags               = var.tags
}

resource "aws_iam_role_policy_attachment" "cluster" {
  for_each = toset([
    "AmazonEKSClusterPolicy", "AmazonEKSComputePolicy", "AmazonEKSBlockStoragePolicy",
    "AmazonEKSLoadBalancingPolicy", "AmazonEKSNetworkingPolicy",
  ])
  role       = aws_iam_role.cluster.name
  policy_arn = "arn:aws:iam::aws:policy/${each.value}"
}

data "aws_iam_policy_document" "node_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "node" {
  name               = "${var.name}-eks-node"
  assume_role_policy = data.aws_iam_policy_document.node_trust.json
  tags               = var.tags
}

resource "aws_iam_role_policy_attachment" "node" {
  for_each   = toset(["AmazonEKSWorkerNodeMinimalPolicy", "AmazonEC2ContainerRegistryPullOnly"])
  role       = aws_iam_role.node.name
  policy_arn = "arn:aws:iam::aws:policy/${each.value}"
}

resource "aws_eks_cluster" "this" {
  name                          = var.name
  role_arn                      = aws_iam_role.cluster.arn
  version                       = var.kubernetes_version
  bootstrap_self_managed_addons = false

  access_config {
    authentication_mode = "API"
  }

  compute_config {
    enabled       = true
    node_pools    = ["general-purpose", "system"]
    node_role_arn = aws_iam_role.node.arn
  }

  kubernetes_network_config {
    elastic_load_balancing {
      enabled = true
    }
  }

  storage_config {
    block_storage {
      enabled = true
    }
  }

  vpc_config {
    subnet_ids              = var.subnet_ids
    endpoint_private_access = true
    endpoint_public_access  = var.public_endpoint
  }

  tags       = var.tags
  depends_on = [aws_iam_role_policy_attachment.cluster]
}

resource "aws_eks_access_entry" "admin" {
  for_each      = toset(var.admin_principal_arns)
  cluster_name  = aws_eks_cluster.this.name
  principal_arn = each.value
}

resource "aws_eks_access_policy_association" "admin" {
  for_each      = toset(var.admin_principal_arns)
  cluster_name  = aws_eks_cluster.this.name
  principal_arn = each.value
  policy_arn    = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"
  access_scope {
    type = "cluster"
  }
  depends_on = [aws_eks_access_entry.admin]
}

# The gateway is the one workload allowed to invoke models (Section 4.5).
resource "aws_eks_pod_identity_association" "proxy" {
  cluster_name    = aws_eks_cluster.this.name
  namespace       = "ai-gateway"
  service_account = "litellm"
  role_arn        = var.gateway_role_arn
  tags            = var.tags
}

# --- State: Aurora Serverless v2 and Valkey ------------------------------------------

resource "aws_security_group" "state" {
  name        = "${var.name}-state"
  description = "Gateway state stores: Postgres and Valkey from the VPC"
  vpc_id      = var.vpc_id
  tags        = var.tags
}

resource "aws_vpc_security_group_ingress_rule" "postgres" {
  security_group_id = aws_security_group.state.id
  cidr_ipv4         = var.vpc_cidr
  from_port         = 5432
  to_port           = 5432
  ip_protocol       = "tcp"
}

resource "aws_vpc_security_group_ingress_rule" "valkey" {
  security_group_id = aws_security_group.state.id
  cidr_ipv4         = var.vpc_cidr
  from_port         = 6379
  to_port           = 6380
  ip_protocol       = "tcp"
}

resource "aws_db_subnet_group" "state" {
  name       = "${var.name}-state"
  subnet_ids = var.subnet_ids
  tags       = var.tags
}

resource "aws_rds_cluster" "state" {
  cluster_identifier                  = "${var.name}-state"
  engine                              = "aurora-postgresql"
  engine_mode                         = "provisioned"
  engine_version                      = "16.6"
  database_name                       = "litellm"
  master_username                     = "litellm_admin"
  manage_master_user_password         = true
  iam_database_authentication_enabled = true
  db_subnet_group_name                = aws_db_subnet_group.state.name
  vpc_security_group_ids              = [aws_security_group.state.id]
  storage_encrypted                   = true
  backup_retention_period             = 7
  skip_final_snapshot                 = true
  serverlessv2_scaling_configuration {
    min_capacity             = var.db_min_acu
    max_capacity             = 4
    seconds_until_auto_pause = var.db_min_acu == 0 ? 600 : null
  }
  tags = var.tags
}

resource "aws_rds_cluster_instance" "state" {
  count              = 1
  identifier         = "${var.name}-state-${count.index}"
  cluster_identifier = aws_rds_cluster.state.id
  instance_class     = "db.serverless"
  engine             = aws_rds_cluster.state.engine
  engine_version     = aws_rds_cluster.state.engine_version
  tags               = var.tags
}

resource "aws_elasticache_serverless_cache" "counters" {
  name                 = "${var.name}-counters"
  engine               = "valkey"
  major_engine_version = "8"
  subnet_ids           = slice(var.subnet_ids, 0, min(length(var.subnet_ids), 3))
  security_group_ids   = [aws_security_group.state.id]
  tags                 = var.tags
}

output "cluster_name" {
  value = aws_eks_cluster.this.name
}
output "cluster_endpoint" {
  value = aws_eks_cluster.this.endpoint
}
output "cluster_ca" {
  value = aws_eks_cluster.this.certificate_authority[0].data
}
output "db_endpoint" {
  value = aws_rds_cluster.state.endpoint
}
output "db_master_secret_arn" {
  value = aws_rds_cluster.state.master_user_secret[0].secret_arn
}
output "valkey_endpoint" {
  value = aws_elasticache_serverless_cache.counters.endpoint[0].address
}
output "valkey_port" {
  value = aws_elasticache_serverless_cache.counters.endpoint[0].port
}
