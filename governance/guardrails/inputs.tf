variable "tags" {
  type    = map(string)
  default = { "managed-by" = "ai-platform-engineering/governance", "cost-center" = "platform" }
}
