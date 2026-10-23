variable "name" {
  type    = string
  default = "platform-gateway"
}

variable "vpc_id" {
  type = string
}

variable "vpc_cidr" {
  type = string
}

variable "subnet_ids" {
  description = "network/ workload subnets, at least two AZs."
  type        = list(string)
}

variable "gateway_role_arn" {
  description = "identity/ gateway role; bound to the proxy's service account by Pod Identity."
  type        = string
}

variable "kubernetes_version" {
  type    = string
  default = "1.33"
}

variable "public_endpoint" {
  description = "Public API endpoint for labs run from a laptop. False in production."
  type        = bool
  default     = true
}

variable "admin_principal_arns" {
  description = "Principals granted cluster admin through access entries."
  type        = list(string)
}

variable "db_min_acu" {
  description = "Aurora Serverless v2 floor. 0 enables auto-pause (lab cost); use >= 0.5 in production."
  type        = number
  default     = 0
}

variable "tags" {
  type    = map(string)
  default = { "managed-by" = "ai-platform-engineering/gateway" }
}
