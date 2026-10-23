# Optional track: AWS Network Firewall (Section 3.3). Adds roughly $9.50/day per AZ
# (endpoint at ~$0.395/hour plus $0.065/GB processed, us-east-1, October 2026).
# Routing: workload → firewall endpoint (same AZ) → NAT → IGW, and the return path
# from the public subnet back through the same endpoint.

resource "aws_networkfirewall_rule_group" "providers" {
  count    = var.enable_network_firewall ? 1 : 0
  name     = "${var.name}-model-providers"
  type     = "STATEFUL"
  capacity = 100
  rule_group {
    rules_source {
      rules_source_list {
        generated_rules_type = "DENYLIST"
        target_types         = ["TLS_SNI", "HTTP_HOST"]
        targets              = [for d in var.blocked_provider_domains : trimprefix(d, "*")]
      }
    }
  }
  tags = var.tags
}

resource "aws_networkfirewall_firewall_policy" "egress" {
  count = var.enable_network_firewall ? 1 : 0
  name  = "${var.name}-egress"
  firewall_policy {
    stateless_default_actions          = ["aws:forward_to_sfe"]
    stateless_fragment_default_actions = ["aws:forward_to_sfe"]
    stateful_rule_group_reference {
      resource_arn = aws_networkfirewall_rule_group.providers[0].arn
    }
  }
  tags = var.tags
}

resource "aws_networkfirewall_firewall" "egress" {
  count               = var.enable_network_firewall ? 1 : 0
  name                = "${var.name}-egress"
  firewall_policy_arn = aws_networkfirewall_firewall_policy.egress[0].arn
  vpc_id              = module.hub.vpc_id
  dynamic "subnet_mapping" {
    for_each = module.hub.firewall_subnet_ids
    content {
      subnet_id = subnet_mapping.value
    }
  }
  tags = var.tags
}

locals {
  # AZ → firewall endpoint ID, from the firewall's sync states.
  fw_endpoint_by_az = var.enable_network_firewall ? {
    for s in aws_networkfirewall_firewall.egress[0].firewall_status[0].sync_states :
    s.availability_zone => s.attachment[0].endpoint_id
  } : {}
}

resource "aws_route" "workload_default_firewall" {
  count                  = var.enable_network_firewall ? length(var.azs) : 0
  route_table_id         = module.hub.workload_route_table_ids[count.index]
  destination_cidr_block = "0.0.0.0/0"
  vpc_endpoint_id        = local.fw_endpoint_by_az[var.azs[count.index]]
}

resource "aws_route" "firewall_to_nat" {
  count                  = var.enable_network_firewall ? length(var.azs) : 0
  route_table_id         = module.hub.firewall_route_table_ids[count.index]
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = module.hub.nat_gateway_ids[count.index]
}

resource "aws_route" "public_return_via_firewall" {
  count                  = var.enable_network_firewall ? length(var.azs) : 0
  route_table_id         = module.hub.public_route_table_ids[count.index]
  destination_cidr_block = cidrsubnet(var.cidr, 4, count.index)
  vpc_endpoint_id        = local.fw_endpoint_by_az[var.azs[count.index]]
}
