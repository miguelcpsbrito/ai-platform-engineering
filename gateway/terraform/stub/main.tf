# gateway/terraform/stub — the minimal platform's gateway (Section 3.6, Table 3.5 step 4):
# the reference custom gateway as a Lambda behind an IAM-authenticated function URL,
# in the hub's workload subnets, calling Bedrock only through the private endpoint.
#
# Build the package first:  make -C gateway package   (writes gateway/build/package/)

terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws     = { source = "hashicorp/aws", version = "~> 6.0" }
    archive = { source = "hashicorp/archive", version = "~> 2.4" }
  }
}

data "aws_caller_identity" "current" {}

data "archive_file" "package" {
  type        = "zip"
  source_dir  = var.package_dir
  output_path = "${path.module}/.build/gateway.zip"
}

resource "aws_security_group" "gateway" {
  name        = "${var.name}-egress"
  description = "Gateway stub: HTTPS to VPC endpoints only"
  vpc_id      = var.vpc_id
  tags        = var.tags
}

resource "aws_vpc_security_group_egress_rule" "https_to_endpoints" {
  security_group_id = aws_security_group.gateway.id
  cidr_ipv4         = var.vpc_cidr
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
}

resource "aws_cloudwatch_log_group" "gateway" {
  name              = "/aws/lambda/${var.name}"
  retention_in_days = var.log_retention_days
  tags              = var.tags
}

resource "aws_iam_role_policy_attachment" "vpc_access" {
  role       = var.role_name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

resource "aws_lambda_function" "gateway" {
  function_name    = var.name
  role             = var.role_arn
  runtime          = "python3.13"
  handler          = "platform_gateway.lambda_handler.handle"
  architectures    = ["arm64"]
  filename         = data.archive_file.package.output_path
  source_code_hash = data.archive_file.package.output_base64sha256
  timeout          = 120
  memory_size      = 512

  environment {
    variables = {
      PLATFORM_ENV            = var.environment
      PLATFORM_CONFIG_DIR     = "/var/task"
      PLATFORM_PROFILE_MAP    = jsonencode(var.profile_map)
      PLATFORM_GUARDRAILS     = jsonencode(var.guardrails)
      PLATFORM_METERING_SINK  = "stdout"
      PLATFORM_CONFIG_VERSION = substr(data.archive_file.package.output_sha256, 0, 12)
      PLATFORM_ACCOUNT_ID     = data.aws_caller_identity.current.account_id
    }
  }

  vpc_config {
    subnet_ids         = var.subnet_ids
    security_group_ids = [aws_security_group.gateway.id]
  }

  logging_config {
    log_format = "Text"
    log_group  = aws_cloudwatch_log_group.gateway.name
  }

  tags = var.tags
}

resource "aws_lambda_function_url" "gateway" {
  function_name      = aws_lambda_function.gateway.function_name
  authorization_type = "AWS_IAM"
}

# Only tenant roles listed in tenant records may invoke (responsibility 1).
resource "aws_lambda_permission" "invoke_url" {
  for_each               = var.invokers
  statement_id           = "url-${each.key}"
  action                 = "lambda:InvokeFunctionUrl"
  function_name          = aws_lambda_function.gateway.function_name
  principal              = each.value
  function_url_auth_type = "AWS_IAM"
}

resource "aws_lambda_permission" "invoke_function" {
  for_each      = var.invokers
  statement_id  = "fn-${each.key}"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.gateway.function_name
  principal     = each.value
}
