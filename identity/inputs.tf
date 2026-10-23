variable "prefix" {
  description = "Role-name prefix. org/ matches platform principals on \"platform-*\" (3.1)."
  type        = string
  default     = "platform"
}

variable "approver_trusted_principal_arns" {
  description = "Who may assume the model-approver role (Identity Center role of the review board, 10.4)."
  type        = list(string)
}

variable "break_glass_trusted_principal_arns" {
  description = "Who may assume break-glass (3.4). Keep to two named people."
  type        = list(string)
}

variable "alert_topic_arn" {
  description = "SNS topic paged on break-glass use. Null disables the target (labs)."
  type        = string
  default     = null
}

variable "enable_identity_center" {
  description = "Create Identity Center permission sets (3.4). False for sandbox labs."
  type        = bool
  default     = false
}

variable "tags" {
  type    = map(string)
  default = { "managed-by" = "ai-platform-engineering/identity" }
}
