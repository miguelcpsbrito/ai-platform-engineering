output "profile_map" {
  description = "tenant|model|region → application profile ARN: the gateway's PLATFORM_PROFILE_MAP."
  value = merge(
    { for k, p in aws_bedrock_inference_profile.primary : k => p.arn },
    { for k, p in aws_bedrock_inference_profile.secondary : k => p.arn },
  )
}
