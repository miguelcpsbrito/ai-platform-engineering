# Inputs for org/. Each variable names the section of the book that motivates it.

variable "enforced_ou_ids" {
  description = "OUs the SCPs and tag policy attach to. Start with the test OU only (3.1)."
  type        = list(string)
}

variable "create_ous" {
  description = "Create the Security/Platform/Workloads/Sandbox/Test OUs (3.1). Set false when Control Tower owns them."
  type        = bool
  default     = false
}

variable "ou_names" {
  description = "OU skeleton of Section 3.1, plus the test OU used to stage SCP changes."
  type        = list(string)
  default     = ["Security", "Platform", "Workloads", "Sandbox", "SCP-Test"]
}

variable "parent_ou_id" {
  description = "Parent for created OUs. Null = organization root. Use a lab OU in a shared organization."
  type        = string
  default     = null
}

variable "platform_principal_arns" {
  description = "Role ARN patterns allowed to set approved-model tags and run batch jobs (3.1, 10.4)."
  type        = list(string)
}

variable "invoke_exempt_principal_arns" {
  description = "Service roles that must invoke models directly, e.g. Knowledge Base ingestion roles (3.1). Keep short."
  type        = list(string)
  default     = ["arn:aws:iam::*:role/platform-kb-ingestion-*"]
}

variable "approved_regions" {
  description = "Regions where AI services may be used — data-residency enforcement (3.1, 10.6)."
  type        = list(string)
  default     = ["us-east-1", "us-west-2"]
}

variable "approved_geographies" {
  description = "Geographic cross-region inference prefixes allowed (3.1). Never include \"global\"."
  type        = list(string)
  default     = ["us"]

  validation {
    condition     = !contains(var.approved_geographies, "global")
    error_message = "global.* profiles may route anywhere in the world; they are excluded by design (Section 3.1)."
  }
}

variable "break_glass_principal_arns" {
  description = "Break-glass roles exempt from the non-Bedrock region restriction (3.4)."
  type        = list(string)
  default     = ["arn:aws:iam::*:role/break-glass-*"]
}

variable "tags" {
  description = "Tags applied to organization resources."
  type        = map(string)
  default     = { "managed-by" = "ai-platform-engineering/org" }
}
