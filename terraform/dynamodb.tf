resource "aws_dynamodb_table" "digests" {
  name         = var.digests_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "date"

  attribute {
    name = "date"
    type = "S"
  }

  # No TTL — sittings don't change once digested.
}

resource "aws_dynamodb_table" "sessions" {
  name         = var.sessions_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "session_id"

  attribute {
    name = "session_id"
    type = "S"
  }

  # AWS auto-deletes rows whose `ttl` attribute is in the past.
  # services/storage.py::put_session always sets ttl = now + 3600.
  ttl {
    enabled        = true
    attribute_name = "ttl"
  }
}
