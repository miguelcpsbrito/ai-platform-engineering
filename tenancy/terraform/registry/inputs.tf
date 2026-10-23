variable "name" {
  type    = string
  default = "platform-tenants"
}

variable "tags" {
  type    = map(string)
  default = { "managed-by" = "ai-platform-engineering/tenancy" }
}
