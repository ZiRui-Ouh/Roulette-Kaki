output "region" {
  description = "Region resources were provisioned in."
  value       = "us-east-1"
}

output "digests_table_name" {
  description = "Name of the DebateDigests DDB table."
  value       = aws_dynamodb_table.digests.name
}

output "sessions_table_name" {
  description = "Name of the ChatSessions DDB table (TTL-enabled)."
  value       = aws_dynamodb_table.sessions.name
}

output "cache_bucket_name" {
  description = "Name of the parl-debate-cache S3 bucket."
  value       = aws_s3_bucket.cache.id
}
