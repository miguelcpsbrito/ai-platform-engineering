output "url" {
  description = "The platform API base URL for the minimal platform."
  value       = aws_lambda_function_url.gateway.function_url
}

output "log_group" {
  value = aws_cloudwatch_log_group.gateway.name
}
