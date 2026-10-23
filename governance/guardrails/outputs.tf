output "guardrails" {
  description = "Risk tier → guardrail id and version: the gateway's PLATFORM_GUARDRAILS."
  value = {
    for k, g in aws_bedrock_guardrail.tier : trimprefix(k, "tier") => {
      guardrailIdentifier = g.guardrail_id
      guardrailVersion    = aws_bedrock_guardrail_version.tier[k].version
    }
  }
}
