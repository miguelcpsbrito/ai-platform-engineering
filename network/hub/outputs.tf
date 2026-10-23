output "vpc_id" { value = aws_vpc.this.id }

output "vpc_cidr" { value = aws_vpc.this.cidr_block }

output "workload_subnet_ids" { value = aws_subnet.workload[*].id }

output "endpoint_subnet_ids" { value = aws_subnet.endpoint[*].id }

output "public_subnet_ids" { value = aws_subnet.public[*].id }

output "firewall_subnet_ids" { value = aws_subnet.firewall[*].id }

output "workload_route_table_ids" { value = aws_route_table.workload[*].id }

output "endpoint_route_table_id" { value = aws_route_table.endpoint.id }

output "public_route_table_ids" { value = aws_route_table.public[*].id }

output "firewall_route_table_ids" { value = aws_route_table.firewall[*].id }

output "nat_gateway_ids" { value = aws_nat_gateway.this[*].id }
