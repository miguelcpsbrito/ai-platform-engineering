# Optional Transit Gateway (Section 3.3): the hub's attachment point for spoke VPCs in
# tenant accounts. Share it with the Workloads OU through RAM; spokes attach from their
# own accounts and route model traffic to the hub's endpoints.

resource "aws_ec2_transit_gateway" "hub" {
  count                           = var.create_transit_gateway ? 1 : 0
  description                     = "${var.name} — AI platform hub"
  default_route_table_association = "enable"
  default_route_table_propagation = "enable"
  auto_accept_shared_attachments  = "disable"
  tags                            = merge(var.tags, { Name = var.name })
}

resource "aws_ec2_transit_gateway_vpc_attachment" "hub" {
  count              = var.create_transit_gateway ? 1 : 0
  transit_gateway_id = aws_ec2_transit_gateway.hub[0].id
  vpc_id             = module.hub.vpc_id
  subnet_ids         = module.hub.endpoint_subnet_ids
  tags               = merge(var.tags, { Name = "${var.name}-hub" })
}

resource "aws_ram_resource_share" "tgw" {
  count                     = var.create_transit_gateway && length(var.tgw_share_principals) > 0 ? 1 : 0
  name                      = "${var.name}-tgw"
  allow_external_principals = false
  tags                      = var.tags
}

resource "aws_ram_resource_association" "tgw" {
  count              = length(aws_ram_resource_share.tgw)
  resource_arn       = aws_ec2_transit_gateway.hub[0].arn
  resource_share_arn = aws_ram_resource_share.tgw[0].arn
}

resource "aws_ram_principal_association" "tgw" {
  for_each           = var.create_transit_gateway ? toset(var.tgw_share_principals) : toset([])
  principal          = each.value
  resource_share_arn = aws_ram_resource_share.tgw[0].arn
}
