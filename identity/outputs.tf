output "tenant_boundary_arn" {
  description = "Permission boundary every tenant role is created under (consumed by every module)."
  value       = aws_iam_policy.tenant_boundary.arn
}

output "gateway_role_arn" {
  description = "Gateway workload role — the network endpoint policy's platform_role_arns."
  value       = aws_iam_role.gateway.arn
}

output "model_approver_role_arn" {
  value = aws_iam_role.model_approver.arn
}

output "break_glass_role_arn" {
  value = aws_iam_role.break_glass.arn
}

output "permission_set_arns" {
  value = { for k, ps in aws_ssoadmin_permission_set.ps : k => ps.arn }
}

output "gateway_role_name" {
  value = aws_iam_role.gateway.name
}
