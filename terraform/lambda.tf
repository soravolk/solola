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

# lambda to run fargate inference
resource "aws_iam_role" "lambda_role" {
  name = "${var.function_name}-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

# Attach basic execution policy (CloudWatch logs)
resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# S3 access policy (for reading audio and writing outputs)
resource "aws_iam_role_policy" "lambda_s3_policy" {
  name = "${var.function_name}-s3-policy"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject"
        ]
        Resource = [
          "${var.s3_bucket_arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:ListBucket"
        ]
        Resource = var.s3_bucket_arn
      }
    ]
  })
}

# Lambda function from ECR image
resource "aws_lambda_function" "inference" {
  function_name = var.function_name
  role          = aws_iam_role.lambda_role.arn
  timeout       = var.lambda_timeout
  memory_size   = var.lambda_memory

  package_type = "Image"
  image_uri    = var.image_uri
  architectures = ["x86_64"]

  # Only configure VPC if subnet_ids are provided
  dynamic "vpc_config" {
    for_each = length(var.subnet_ids) > 0 ? [1] : []
    content {
      subnet_ids         = var.subnet_ids
      security_group_ids = var.security_group_ids
    }
  }

  environment {
    variables = {
      S3_BUCKET_NAME       = var.s3_bucket_name
      NUMBA_CACHE_DIR      = "/tmp/numba_cache"
      NUMBA_DISABLE_JIT    = "0"
      MPLCONFIGDIR         = "/tmp/matplotlib"
      # Fargate configuration (for handler_fargate.py)
      ECS_CLUSTER          = aws_ecs_cluster.inference.name
      ECS_TASK_DEFINITION  = aws_ecs_task_definition.inference.family
      ECS_SUBNETS          = join(",", [aws_subnet.public_1.id, aws_subnet.public_2.id])
      ECS_SECURITY_GROUPS  = aws_security_group.fargate.id
    }
  }

  tags = var.tags
}