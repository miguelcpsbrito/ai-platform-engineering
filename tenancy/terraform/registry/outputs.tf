output "table_name" {
  value = aws_dynamodb_table.tenants.name
}

output "table_arn" {
  value = aws_dynamodb_table.tenants.arn
}
