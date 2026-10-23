# network/hub — the hub VPC: workload, endpoint, public (NAT) and optional firewall subnets.

terraform {
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 6.0" }
  }
}

locals {
  n = length(var.azs)
  # /16 → /20 blocks: 0..n-1 workloads, 4.. endpoints, 8.. public, 12.. firewall
  workload_cidrs = [for i in range(local.n) : cidrsubnet(var.cidr, 4, i)]
  endpoint_cidrs = [for i in range(local.n) : cidrsubnet(var.cidr, 4, i + 4)]
  public_cidrs   = [for i in range(local.n) : cidrsubnet(var.cidr, 4, i + 8)]
  firewall_cidrs = [for i in range(local.n) : cidrsubnet(var.cidr, 4, i + 12)]
}

resource "aws_vpc" "this" {
  cidr_block           = var.cidr
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = merge(var.tags, { Name = var.name })
}

resource "aws_subnet" "workload" {
  count             = local.n
  vpc_id            = aws_vpc.this.id
  cidr_block        = local.workload_cidrs[count.index]
  availability_zone = var.azs[count.index]
  tags              = merge(var.tags, { Name = "${var.name}-workload-${var.azs[count.index]}", tier = "workload" })
}

resource "aws_subnet" "endpoint" {
  count             = local.n
  vpc_id            = aws_vpc.this.id
  cidr_block        = local.endpoint_cidrs[count.index]
  availability_zone = var.azs[count.index]
  tags              = merge(var.tags, { Name = "${var.name}-endpoint-${var.azs[count.index]}", tier = "endpoint" })
}

resource "aws_subnet" "public" {
  count             = var.enable_nat ? local.n : 0
  vpc_id            = aws_vpc.this.id
  cidr_block        = local.public_cidrs[count.index]
  availability_zone = var.azs[count.index]
  tags              = merge(var.tags, { Name = "${var.name}-public-${var.azs[count.index]}", tier = "public" })
}

resource "aws_subnet" "firewall" {
  count             = var.enable_firewall_subnets ? local.n : 0
  vpc_id            = aws_vpc.this.id
  cidr_block        = local.firewall_cidrs[count.index]
  availability_zone = var.azs[count.index]
  tags              = merge(var.tags, { Name = "${var.name}-firewall-${var.azs[count.index]}", tier = "firewall" })
}

resource "aws_internet_gateway" "this" {
  count  = var.enable_nat ? 1 : 0
  vpc_id = aws_vpc.this.id
  tags   = merge(var.tags, { Name = var.name })
}

resource "aws_eip" "nat" {
  count  = var.enable_nat ? local.n : 0
  domain = "vpc"
  tags   = merge(var.tags, { Name = "${var.name}-nat-${var.azs[count.index]}" })
}

resource "aws_nat_gateway" "this" {
  count         = var.enable_nat ? local.n : 0
  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id
  tags          = merge(var.tags, { Name = "${var.name}-${var.azs[count.index]}" })
}

# Route tables are per AZ so the Network Firewall track can keep routing symmetric.
resource "aws_route_table" "public" {
  count  = var.enable_nat ? local.n : 0
  vpc_id = aws_vpc.this.id
  tags   = merge(var.tags, { Name = "${var.name}-public-${var.azs[count.index]}" })
}

resource "aws_route" "public_igw" {
  count                  = var.enable_nat ? local.n : 0
  route_table_id         = aws_route_table.public[count.index].id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.this[0].id
}

resource "aws_route_table_association" "public" {
  count          = var.enable_nat ? local.n : 0
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public[count.index].id
}

resource "aws_route_table" "firewall" {
  count  = var.enable_firewall_subnets ? local.n : 0
  vpc_id = aws_vpc.this.id
  tags   = merge(var.tags, { Name = "${var.name}-firewall-${var.azs[count.index]}" })
}

resource "aws_route_table_association" "firewall" {
  count          = var.enable_firewall_subnets ? local.n : 0
  subnet_id      = aws_subnet.firewall[count.index].id
  route_table_id = aws_route_table.firewall[count.index].id
}

# One route table per AZ for workloads, so the firewall track can steer per AZ.
resource "aws_route_table" "workload" {
  count  = local.n
  vpc_id = aws_vpc.this.id
  tags   = merge(var.tags, { Name = "${var.name}-workload-${var.azs[count.index]}" })
}

resource "aws_route_table_association" "workload" {
  count          = local.n
  subnet_id      = aws_subnet.workload[count.index].id
  route_table_id = aws_route_table.workload[count.index].id
}

resource "aws_route_table" "endpoint" {
  vpc_id = aws_vpc.this.id
  tags   = merge(var.tags, { Name = "${var.name}-endpoint" })
}

resource "aws_route_table_association" "endpoint" {
  count          = local.n
  subnet_id      = aws_subnet.endpoint[count.index].id
  route_table_id = aws_route_table.endpoint.id
}
