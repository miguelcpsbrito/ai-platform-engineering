output "internal_url" {
  description = "Behind the platform DNS name (ai.platform.internal) in production."
  value       = try("http://${data.kubernetes_ingress_v1.litellm.status[0].load_balancer[0].ingress[0].hostname}", null)
}
