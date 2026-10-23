# finops/terraform — the Chapter 6 pipeline's AWS half: CUR 2.0 through AWS Data Exports,
# the gateway's metering stream (Firehose → S3, partitioned by day), the Glue database
# and an Athena workgroup with a scan limit. The allocation SQL runs from finops/lib.
# CUR 2.0 can be delivered cross-account straight into Log Archive (April 2026); this
# module writes to a bucket in the account it runs in — point it there.

terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 6.0" }
  }
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  account = data.aws_caller_identity.current.account_id
  region  = data.aws_region.current.region
}

resource "aws_s3_bucket" "raw" {
  bucket = "${var.prefix}-raw-${local.account}"
  tags   = var.tags
}

resource "aws_s3_bucket" "curated" {
  bucket = "${var.prefix}-curated-${local.account}"
  tags   = var.tags
}

resource "aws_s3_bucket_public_access_block" "raw" {
  bucket                  = aws_s3_bucket.raw.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_public_access_block" "curated" {
  bucket                  = aws_s3_bucket.curated.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Data Exports writes CUR 2.0 into the raw bucket.
data "aws_iam_policy_document" "raw_bucket" {
  statement {
    sid       = "AllowDataExports"
    actions   = ["s3:PutObject", "s3:GetBucketPolicy"]
    resources = [aws_s3_bucket.raw.arn, "${aws_s3_bucket.raw.arn}/*"]
    principals {
      type        = "Service"
      identifiers = ["bcm-data-exports.amazonaws.com", "billingreports.amazonaws.com"]
    }
    condition {
      test     = "StringLike"
      variable = "aws:SourceAccount"
      values   = [local.account]
    }
  }
}

resource "aws_s3_bucket_policy" "raw" {
  bucket = aws_s3_bucket.raw.id
  policy = data.aws_iam_policy_document.raw_bucket.json
}

resource "aws_bcmdataexports_export" "cur2" {
  export {
    name        = "${var.prefix}-cur2"
    description = "CUR 2.0 for AI allocation (Chapter 6)"
    data_query {
      query_statement = "SELECT bill_billing_period_start_date, line_item_usage_start_date, line_item_usage_account_id, line_item_line_item_type, line_item_product_code, line_item_usage_type, line_item_resource_id, line_item_usage_amount, line_item_unblended_cost, resource_tags FROM COST_AND_USAGE_REPORT"
      table_configurations = {
        COST_AND_USAGE_REPORT = {
          TIME_GRANULARITY                      = "DAILY"
          INCLUDE_RESOURCES                     = "TRUE"
          INCLUDE_MANUAL_DISCOUNT_COMPATIBILITY = "FALSE"
          INCLUDE_SPLIT_COST_ALLOCATION_DATA    = "FALSE"
        }
      }
    }
    destination_configurations {
      s3_destination {
        s3_bucket = aws_s3_bucket.raw.bucket
        s3_prefix = "cur2"
        s3_region = local.region
        s3_output_configurations {
          overwrite   = "OVERWRITE_REPORT"
          format      = "PARQUET"
          compression = "PARQUET"
          output_type = "CUSTOM"
        }
      }
    }
    refresh_cadence {
      frequency = "SYNCHRONOUS"
    }
  }
  tags       = var.tags
  depends_on = [aws_s3_bucket_policy.raw]
}

# --- the gateway's metering stream ---------------------------------------------------

data "aws_iam_policy_document" "firehose_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["firehose.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "firehose" {
  name               = "${var.prefix}-metering-firehose"
  assume_role_policy = data.aws_iam_policy_document.firehose_trust.json
  tags               = var.tags
}

data "aws_iam_policy_document" "firehose" {
  statement {
    actions   = ["s3:PutObject", "s3:AbortMultipartUpload", "s3:GetBucketLocation", "s3:ListBucket"]
    resources = [aws_s3_bucket.raw.arn, "${aws_s3_bucket.raw.arn}/*"]
  }
}

resource "aws_iam_role_policy" "firehose" {
  name   = "write-raw"
  role   = aws_iam_role.firehose.id
  policy = data.aws_iam_policy_document.firehose.json
}

resource "aws_kinesis_firehose_delivery_stream" "metering" {
  name        = "${var.prefix}-metering"
  destination = "extended_s3"
  extended_s3_configuration {
    role_arn            = aws_iam_role.firehose.arn
    bucket_arn          = aws_s3_bucket.raw.arn
    prefix              = "gateway-events/dt=!{timestamp:yyyy-MM-dd}/"
    error_output_prefix = "gateway-events-errors/!{firehose:error-output-type}/dt=!{timestamp:yyyy-MM-dd}/"
    buffering_interval  = 60
    buffering_size      = 64
    compression_format  = "GZIP"
  }
  tags = var.tags
}

# --- catalog and query ---------------------------------------------------------------

resource "aws_glue_catalog_database" "finops" {
  name = "finops"
}

resource "aws_athena_workgroup" "finops" {
  name          = "finops"
  force_destroy = true
  configuration {
    enforce_workgroup_configuration    = true
    bytes_scanned_cutoff_per_query     = var.athena_bytes_scanned_cutoff
    publish_cloudwatch_metrics_enabled = true
    result_configuration {
      output_location = "s3://${aws_s3_bucket.curated.bucket}/athena-results/"
    }
  }
  tags = var.tags
}
