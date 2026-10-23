variable "name" {
  description = "Collection name: 3–28 lowercase characters."
  type        = string
  default     = "platform-chunks"
}

variable "vpc_id" {
  type = string
}

variable "subnet_ids" {
  type = list(string)
}

variable "security_group_ids" {
  type = list(string)
}

variable "reader_role_arns" {
  description = "Roles that query (the platform retrieval library's callers)."
  type        = list(string)
}

variable "writer_role_arns" {
  description = "Roles that ingest (blueprint ingestion jobs)."
  type        = list(string)
}

variable "tags" {
  type    = map(string)
  default = { "managed-by" = "ai-platform-engineering/tenancy" }
}
