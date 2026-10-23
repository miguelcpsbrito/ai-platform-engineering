output "metering_stream" {
  value = aws_kinesis_firehose_delivery_stream.metering.name
}

output "raw_bucket" {
  value = aws_s3_bucket.raw.bucket
}

output "curated_bucket" {
  value = aws_s3_bucket.curated.bucket
}

output "athena_workgroup" {
  value = aws_athena_workgroup.finops.name
}
