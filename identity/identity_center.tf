# Identity Center permission sets for the personas of Section 2.4. Optional, because a
# lab sandbox usually has no Identity Center instance it may modify.

data "aws_ssoadmin_instances" "this" {
  count = var.enable_identity_center ? 1 : 0
}

locals {
  sso_instance_arn = var.enable_identity_center ? tolist(data.aws_ssoadmin_instances.this[0].arns)[0] : null
  permission_sets = {
    PlatformEngineer = { duration = "PT4H", managed = ["arn:aws:iam::aws:policy/PowerUserAccess"] }
    TenantDeveloper  = { duration = "PT8H", managed = ["arn:aws:iam::aws:policy/ReadOnlyAccess"] }
    Auditor          = { duration = "PT2H", managed = ["arn:aws:iam::aws:policy/SecurityAudit"] }
  }
  ps_attachments = merge([
    for name, ps in local.permission_sets : {
      for arn in ps.managed : "${name}|${arn}" => { name = name, arn = arn }
    }
  ]...)
}

resource "aws_ssoadmin_permission_set" "ps" {
  for_each         = var.enable_identity_center ? local.permission_sets : {}
  name             = each.key
  instance_arn     = local.sso_instance_arn
  session_duration = each.value.duration
  tags             = var.tags
}

resource "aws_ssoadmin_managed_policy_attachment" "ps" {
  for_each           = var.enable_identity_center ? local.ps_attachments : {}
  instance_arn       = local.sso_instance_arn
  permission_set_arn = aws_ssoadmin_permission_set.ps[each.value.name].arn
  managed_policy_arn = each.value.arn
}

# TenantDeveloper sessions carry the tenant boundary as their ceiling.
resource "aws_ssoadmin_permissions_boundary_attachment" "tenant" {
  count              = var.enable_identity_center ? 1 : 0
  instance_arn       = local.sso_instance_arn
  permission_set_arn = aws_ssoadmin_permission_set.ps["TenantDeveloper"].arn
  permissions_boundary {
    customer_managed_policy_reference {
      name = aws_iam_policy.tenant_boundary.name
    }
  }
}
