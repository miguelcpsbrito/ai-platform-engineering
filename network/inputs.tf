variable "name" {
  description = "Name prefix for the hub (3.3)."
  type        = string
  default     = "platform-hub"
}

variable "region" {
  description = "Home region; must be in org/'s approved_regions (3.1)."
  type        = string
}

variable "cidr" {
  description = "Hub VPC CIDR. Plan it with the Transit Gateway attachments in mind (3.3)."
  type        = string
  default     = "10.40.0.0/16"
}

variable "azs" {
  description = "Availability Zones. Two for labs; three for production (9.3)."
  type        = list(string)
}

variable "enable_nat" {
  description = "NAT egress for workloads. Required by both egress tracks."
  type        = bool
  default     = true
}

variable "enable_network_firewall" {
  description = "Optional Network Firewall track (3.3). Adds about $9.50/day per AZ."
  type        = bool
  default     = false
}

variable "platform_role_arns" {
  description = "Roles allowed through the bedrock-runtime endpoint — the gateway's, normally (Figure 3.4)."
  type        = list(string)
}

variable "blocked_provider_domains" {
  description = "Reviewed list of external model-provider domains turned into NXDOMAIN (3.3)."
  type        = list(string)
  default = [
    "api.openai.com", "*.openai.com",
    "api.anthropic.com",
    "generativelanguage.googleapis.com",
    "api.mistral.ai", "api.cohere.ai", "api.cohere.com",
    "api.groq.com", "api.together.xyz", "api.deepseek.com",
    "openrouter.ai", "*.openrouter.ai",
  ]
}

variable "extra_interface_services" {
  description = "Additional interface endpoints, e.g. [\"ecr.api\", \"ecr.dkr\"] for EKS nodes."
  type        = list(string)
  default     = []
}

variable "log_retention_days" {
  description = "Retention for resolver query logs (evidence for 10.4)."
  type        = number
  default     = 90
}

variable "tags" {
  type    = map(string)
  default = { "managed-by" = "ai-platform-engineering/network" }
}
