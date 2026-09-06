variable "region" {
  description = "AWS region for all resources. Bedrock Nova is in us-east-1."
  type        = string
  default     = "us-east-1"
}

variable "digests_table_name" {
  description = "DDB table caching per-date parliament digests. PK: date."
  type        = string
  default     = "DebateDigests"
}

variable "sessions_table_name" {
  description = "DDB table storing chat sessions with 1h TTL. PK: session_id."
  type        = string
  default     = "ChatSessions"
}

variable "cache_bucket_name" {
  description = "S3 bucket caching raw SPRS report bytes. Keyed {date}/{topic_id}.{ext}."
  type        = string
  default     = "parl-debate-cache-v2"
}
