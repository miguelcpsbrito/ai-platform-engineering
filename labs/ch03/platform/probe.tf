# Egress probe (Table 3.5 step 2): a Lambda in a workload subnet that resolves an
# external provider and the Bedrock endpoint, so the proof runs from inside the VPC.

data "archive_file" "probe" {
  type        = "zip"
  source_file = "${path.module}/probe.py"
  output_path = "${path.module}/.build/probe.zip"
}

data "aws_iam_policy_document" "probe_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "probe" {
  name                 = "lab-egress-probe"
  assume_role_policy   = data.aws_iam_policy_document.probe_trust.json
  permissions_boundary = module.identity.tenant_boundary_arn
}

resource "aws_iam_role_policy_attachment" "probe" {
  role       = aws_iam_role.probe.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

resource "aws_security_group" "probe" {
  name        = "lab-egress-probe"
  description = "Egress probe"
  vpc_id      = module.network.vpc_id
}

resource "aws_vpc_security_group_egress_rule" "probe_all" {
  security_group_id = aws_security_group.probe.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}

resource "aws_lambda_function" "probe" {
  function_name    = "lab-egress-probe"
  role             = aws_iam_role.probe.arn
  runtime          = "python3.13"
  handler          = "probe.handler"
  filename         = data.archive_file.probe.output_path
  source_code_hash = data.archive_file.probe.output_base64sha256
  timeout          = 30
  vpc_config {
    subnet_ids         = module.network.workload_subnet_ids
    security_group_ids = [aws_security_group.probe.id]
  }
}

output "probe_function" {
  value = aws_lambda_function.probe.function_name
}
