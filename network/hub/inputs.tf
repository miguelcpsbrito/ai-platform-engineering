variable "name" { type = string }

variable "cidr" { type = string }

variable "azs" { type = list(string) }

variable "enable_nat" {
  type    = bool
  default = true
}

variable "enable_firewall_subnets" {
  type    = bool
  default = false
}

variable "tags" {
  type    = map(string)
  default = {}
}
