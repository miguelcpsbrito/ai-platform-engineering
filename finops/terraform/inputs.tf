variable "prefix" {
  type    = string
  default = "platform-finops"
}

variable "gateway_role_arn" {
  description = "identity/ gateway role: the only producer on the metering stream."
  type        = string
}

variable "athena_bytes_scanned_cutoff" {
  type    = number
  default = 10737418240 # 10 GiB per query
}

variable "tags" {
  type    = map(string)
  default = { "managed-by" = "ai-platform-engineering/finops", "cost-center" = "platform" }
}
