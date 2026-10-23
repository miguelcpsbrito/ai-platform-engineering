output "ou_ids" {
  description = "Created OU IDs by name (consumed by tenancy/)."
  value       = { for k, ou in aws_organizations_organizational_unit.ou : k => ou.id }
}

output "scp_ids" {
  description = "SCP IDs by name (consumed by governance/ evidence reports)."
  value       = { for k, p in aws_organizations_policy.scp : k => p.id }
}

output "tag_policy_id" {
  description = "Tag policy ID."
  value       = aws_organizations_policy.ai_tags.id
}

output "rendered_scps" {
  description = "Rendered SCP documents, for review in plan output and for org/tests."
  value       = { for k, p in aws_organizations_policy.scp : k => p.content }
}
