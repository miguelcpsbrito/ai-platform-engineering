variable "tenant" {
  description = "Stable tenant ID from the tenant record (5.6)."
  type        = string
}

variable "monthly_budget_usd" {
  type = number
}

variable "alert_emails" {
  description = "The tenant team's channel address (an email-to-channel bridge works)."
  type        = list(string)
}

variable "tags" {
  type    = map(string)
  default = {}
}
