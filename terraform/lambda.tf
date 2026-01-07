# IAM Role for API Lambda
resource "aws_iam_role" "api_lambda_role" {
  name = "eg-solo-api-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })

  tags = {
    Name    = "eg-solo-api-lambda-role"
    Project = "eg-solo"
  }
}

# Attach basic Lambda execution policy
resource "aws_iam_role_policy_attachment" "api_lambda_basic" {
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
  role       = aws_iam_role.api_lambda_role.name
}

# S3 permissions for presigned URL generation
resource "aws_iam_role_policy" "api_lambda_s3" {
  name = "s3-presigned-url-access"
  role = aws_iam_role.api_lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "s3:PutObject",
        "s3:PutObjectAcl",
        "s3:GetObject"
      ]
      Resource = "${var.s3_bucket_arn}/*"
    }]
  })
}

# Lambda Function
resource "aws_lambda_function" "api_handler" {
  function_name = var.api_function_name
  role          = aws_iam_role.api_lambda_role.arn
  package_type  = "Image"
  image_uri     = var.api_image_uri
  timeout       = var.api_lambda_timeout
  memory_size   = var.api_lambda_memory

  environment {
    variables = {
      S3_BUCKET_NAME = var.s3_bucket_name
    }
  }

  tags = {
    Name    = var.api_function_name
    Project = "eg-solo"
  }
}

# CloudWatch Log Group for API Lambda
resource "aws_cloudwatch_log_group" "api_lambda" {
  name              = "/aws/lambda/${var.api_function_name}"
  retention_in_days = 7

  tags = {
    Name    = "${var.api_function_name}-logs"
    Project = "eg-solo"
  }
}
