variable "name" {
  type    = string
  default = "platform-gateway-stub"
}

variable "package_dir" {
  description = "Directory produced by `make -C gateway package`."
  type        = string
}

variable "role_arn" {
  description = "identity/'s gateway_role_arn (trusts lambda.amazonaws.com)."
  type        = string
}

variable "role_name" {
  type = string
}

variable "subnet_ids" {
  type = list(string)
}

variable "vpc_id" {
  type = string
}

variable "vpc_cidr" {
  type = string
}

variable "profile_map" {
  description = "gateway/terraform/profiles output: tenant|model|region → profile ARN."
  type        = map(string)
}

variable "guardrails" {
  description = "Risk tier → {guardrailIdentifier, guardrailVersion}. Empty until Chapter 10."
  type        = map(object({ guardrailIdentifier = string, guardrailVersion = string }))
  default     = {}
}

variable "environment" {
  type    = string
  default = "prod"
}

variable "invokers" {
  description = "Tenant workload roles allowed to call the function URL, by a static name (plan-safe keys)."
  type        = map(string)
}

variable "log_retention_days" {
  type    = number
  default = 30
}

variable "tags" {
  type    = map(string)
  default = { "managed-by" = "ai-platform-engineering/gateway" }
}
