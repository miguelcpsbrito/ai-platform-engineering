# network/ — hub VPC, private endpoints, egress control (Section 3.3, Figure 3.4).
# Default track: DNS Firewall (NXDOMAIN + query log). Optional: Network Firewall.

module "hub" {
  source                  = "./hub"
  name                    = var.name
  cidr                    = var.cidr
  azs                     = var.azs
  enable_nat              = var.enable_nat
  enable_firewall_subnets = var.enable_network_firewall
  tags                    = var.tags
}

locals {
  rt_svc = "com.amazonaws.${var.region}.bedrock-runtime"
  dl     = aws_route53_resolver_firewall_domain_list.providers
  rg     = aws_route53_resolver_firewall_rule_group.egress

  # Interface endpoints the platform needs besides bedrock-runtime.
  interface_services = toset(concat(
    ["bedrock", "sts", "logs", "secretsmanager", "monitoring"],
    var.extra_interface_services,
  ))
}

resource "aws_security_group" "endpoints" {
  name        = "${var.name}-endpoints"
  description = "HTTPS from the hub VPC to interface endpoints"
  vpc_id      = module.hub.vpc_id
  tags        = var.tags
}

resource "aws_vpc_security_group_ingress_rule" "endpoints_https" {
  security_group_id = aws_security_group.endpoints.id
  cidr_ipv4         = var.cidr
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
}

# Figure 3.4 — only platform roles may invoke models through the runtime endpoint.
resource "aws_vpc_endpoint" "bedrock_runtime" {
  vpc_id              = module.hub.vpc_id
  service_name        = local.rt_svc
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true
  subnet_ids          = module.hub.endpoint_subnet_ids
  security_group_ids  = [aws_security_group.endpoints.id]
  policy = jsonencode({
    Statement = [{
      Effect    = "Allow"
      Principal = { AWS = var.platform_role_arns }
      Action = ["bedrock:InvokeModel",
      "bedrock:InvokeModelWithResponseStream"]
      Resource = "*"
    }]
  })
  tags = merge(var.tags, { Name = "${var.name}-bedrock-runtime" })
}

resource "aws_vpc_endpoint" "interface" {
  for_each            = local.interface_services
  vpc_id              = module.hub.vpc_id
  service_name        = "com.amazonaws.${var.region}.${each.value}"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true
  subnet_ids          = module.hub.endpoint_subnet_ids
  security_group_ids  = [aws_security_group.endpoints.id]
  tags                = merge(var.tags, { Name = "${var.name}-${each.value}" })
}

resource "aws_vpc_endpoint" "s3" {
  vpc_id            = module.hub.vpc_id
  service_name      = "com.amazonaws.${var.region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = module.hub.workload_route_table_ids
  tags              = merge(var.tags, { Name = "${var.name}-s3" })
}

# --- Egress control, default track: Route 53 Resolver DNS Firewall -----------------

resource "aws_route53_resolver_firewall_domain_list" "providers" {
  name    = "external-model-providers"
  domains = var.blocked_provider_domains # reviewed list
  tags    = var.tags
}

resource "aws_route53_resolver_firewall_rule_group" "egress" {
  name = "${var.name}-ai-egress"
  tags = var.tags
}

resource "aws_route53_resolver_firewall_rule" "block_providers" {
  name                    = "block-external-model-providers"
  action                  = "BLOCK"
  block_response          = "NXDOMAIN"
  firewall_domain_list_id = local.dl.id
  firewall_rule_group_id  = local.rg.id
  priority                = 100
}

resource "aws_route53_resolver_firewall_rule_group_association" "hub" {
  name                   = "${var.name}-ai-egress"
  firewall_rule_group_id = local.rg.id
  vpc_id                 = module.hub.vpc_id
  priority               = 101
  tags                   = var.tags
}

# Every blocked lookup is evidence (Section 3.3): log queries to CloudWatch.
resource "aws_cloudwatch_log_group" "dns" {
  name              = "/platform/network/${var.name}/resolver-queries"
  retention_in_days = var.log_retention_days
  tags              = var.tags
}

resource "aws_route53_resolver_query_log_config" "hub" {
  name            = "${var.name}-queries"
  destination_arn = aws_cloudwatch_log_group.dns.arn
  tags            = var.tags
}

resource "aws_route53_resolver_query_log_config_association" "hub" {
  resolver_query_log_config_id = aws_route53_resolver_query_log_config.hub.id
  resource_id                  = module.hub.vpc_id
}

# Default route for workloads: NAT, unless the Network Firewall track steers it.
resource "aws_route" "workload_default_nat" {
  count                  = var.enable_nat && !var.enable_network_firewall ? length(var.azs) : 0
  route_table_id         = module.hub.workload_route_table_ids[count.index]
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = module.hub.nat_gateway_ids[count.index]
}
