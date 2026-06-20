# DynamoDB table for IP-based rate limiting of AI fix requests
resource "aws_dynamodb_table" "rate_limit" {
  name         = "solola-rate-limit"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "user_id"  # Note: still named 'user_id' but stores IP addresses

  attribute {
    name = "user_id"
    type = "S"
  }

  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  tags = {
    Name    = "solola-rate-limit"
    Project = "eg-solo"
  }
}

# IAM policy for API Lambda to access rate limit table
resource "aws_iam_role_policy" "api_lambda_rate_limit" {
  name = "dynamodb-rate-limit-access"
  role = aws_iam_role.api_lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:UpdateItem"
      ]
      Resource = aws_dynamodb_table.rate_limit.arn
    }]
  })
}
