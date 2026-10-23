output "cluster_name" {
  value = aws_eks_cluster.this.name
}

output "cluster_endpoint" {
  value = aws_eks_cluster.this.endpoint
}

output "cluster_ca" {
  value = aws_eks_cluster.this.certificate_authority[0].data
}

output "db_endpoint" {
  value = aws_rds_cluster.state.endpoint
}

output "db_master_secret_arn" {
  value = aws_rds_cluster.state.master_user_secret[0].secret_arn
}

output "valkey_endpoint" {
  value = aws_elasticache_serverless_cache.counters.endpoint[0].address
}

output "valkey_port" {
  value = aws_elasticache_serverless_cache.counters.endpoint[0].port
}
