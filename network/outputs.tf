output "vpc_id" {
  description = "Hub VPC (consumed by gateway/, tenancy/, observability/)."
  value       = module.hub.vpc_id
}

output "workload_subnet_ids" {
  value = module.hub.workload_subnet_ids
}

output "endpoint_subnet_ids" {
  value = module.hub.endpoint_subnet_ids
}

output "endpoint_ids" {
  description = "Interface endpoint IDs by service."
  value = merge(
    { "bedrock-runtime" = aws_vpc_endpoint.bedrock_runtime.id },
    { for k, e in aws_vpc_endpoint.interface : k => e.id },
  )
}

output "resolver_rule_group_id" {
  description = "DNS Firewall rule group, for association with spoke VPCs."
  value       = aws_route53_resolver_firewall_rule_group.egress.id
}

output "dns_query_log_group" {
  value = aws_cloudwatch_log_group.dns.name
}

output "vpc_cidr" {
  value = var.cidr
}

output "transit_gateway_id" {
  value = try(aws_ec2_transit_gateway.hub[0].id, null)
}
