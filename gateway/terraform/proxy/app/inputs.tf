variable "rendered_config_file" {
  description = "build/litellm/litellm-config.yaml from `make -C gateway render`."
  type        = string
}

variable "chart_repository" {
  description = "Where the LiteLLM chart is published. Check the LiteLLM docs at deploy time."
  type        = string
  default     = "oci://docker.litellm.ai/berriai"
}

variable "chart_version" {
  type    = string
  default = "1.1.3"
}

variable "image_tag" {
  description = "Proxy image tag, pinned. Must match the version the conformance suite last passed."
  type        = string
  default     = "v1.85.1"
}

variable "db_host" {
  type = string
}

variable "db_user" {
  description = "Database user granted rds_iam (IAM authentication, no password in the cluster)."
  type        = string
  default     = "litellm"
}

variable "valkey_host" {
  type = string
}

variable "valkey_port" {
  type = number
}

variable "replicas" {
  type    = number
  default = 3
}
