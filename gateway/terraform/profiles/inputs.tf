variable "profiles" {
  description = "Output of platform_gateway.profiles: [{key, tenant, model, region, cost_center, name}]."
  type = list(object({
    key         = string, tenant = string, model = string, region = string,
    cost_center = string, name = string
  }))
}

variable "primary_region" {
  type = string
}

variable "secondary_region" {
  type = string
}

variable "tags" {
  type    = map(string)
  default = { "managed-by" = "ai-platform-engineering/gateway" }
}
