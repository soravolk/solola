# WebSocket API Gateway
resource "aws_apigatewayv2_api" "websocket" {
  name                       = "eg-solo-websocket-api"
  protocol_type              = "WEBSOCKET"
  route_selection_expression = "$request.body.action"
  description                = "WebSocket API for EG Solo real-time updates"

  tags = {
    Name    = "eg-solo-websocket-api"
    Project = "eg-solo"
  }
}

# IAM Role for WebSocket Lambda
resource "aws_iam_role" "websocket_lambda_role" {
  name = "eg-solo-websocket-lambda-role"

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
    Name    = "eg-solo-websocket-lambda-role"
    Project = "eg-solo"
  }
}

# Single inline policy with all permissions
resource "aws_iam_role_policy" "websocket_lambda_policy" {
  name = "websocket-lambda-policy"
  role = aws_iam_role.websocket_lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "execute-api:ManageConnections"
        ]
        Resource = "arn:aws:execute-api:${var.aws_region}:*:${aws_apigatewayv2_api.websocket.id}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:Query",
          "dynamodb:DeleteItem",
          "dynamodb:UpdateItem"
        ]
        Resource = [
          aws_dynamodb_table.websocket_connections.arn,
          "${aws_dynamodb_table.websocket_connections.arn}/index/*"
        ]
      }
    ]
  })
}

# Lambda function for WebSocket handler (single handler for all routes)
resource "aws_lambda_function" "websocket_handler" {
  filename         = "${path.module}/lambda-websocket.zip"
  function_name    = "eg-solo-websocket-handler"
  role            = aws_iam_role.websocket_lambda_role.arn
  handler         = "index.handler"
  source_code_hash = filebase64sha256("${path.module}/lambda-websocket.zip")
  runtime         = "nodejs18.x"
  timeout         = 30

  environment {
    variables = {
      WEBSOCKET_API_ID = aws_apigatewayv2_api.websocket.id
    }
  }

  tags = {
    Name    = "eg-solo-websocket-handler"
    Project = "eg-solo"
  }
}

# CloudWatch Log Group for WebSocket Lambda
resource "aws_cloudwatch_log_group" "websocket_lambda" {
  name              = "/aws/lambda/eg-solo-websocket-handler"
  retention_in_days = 7

  tags = {
    Name    = "eg-solo-websocket-handler-logs"
    Project = "eg-solo"
  }
}

# Lambda permission for API Gateway to invoke
resource "aws_lambda_permission" "websocket_apigw" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.websocket_handler.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.websocket.execution_arn}/*/*"
}

# Integration
resource "aws_apigatewayv2_integration" "websocket_lambda" {
  api_id           = aws_apigatewayv2_api.websocket.id
  integration_type = "AWS_PROXY"
  integration_uri  = aws_lambda_function.websocket_handler.invoke_arn
}

# Routes
resource "aws_apigatewayv2_route" "connect" {
  api_id    = aws_apigatewayv2_api.websocket.id
  route_key = "$connect"
  target    = "integrations/${aws_apigatewayv2_integration.websocket_lambda.id}"
}

resource "aws_apigatewayv2_route" "disconnect" {
  api_id    = aws_apigatewayv2_api.websocket.id
  route_key = "$disconnect"
  target    = "integrations/${aws_apigatewayv2_integration.websocket_lambda.id}"
}

resource "aws_apigatewayv2_route" "default" {
  api_id    = aws_apigatewayv2_api.websocket.id
  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.websocket_lambda.id}"
}

# Deployment
resource "aws_apigatewayv2_deployment" "websocket" {
  api_id = aws_apigatewayv2_api.websocket.id

  depends_on = [
    aws_apigatewayv2_route.connect,
    aws_apigatewayv2_route.disconnect,
    aws_apigatewayv2_route.default
  ]

  triggers = {
    redeployment = sha1(join(",", tolist([
      jsonencode(aws_apigatewayv2_integration.websocket_lambda),
      jsonencode(aws_apigatewayv2_route.connect),
      jsonencode(aws_apigatewayv2_route.disconnect),
      jsonencode(aws_apigatewayv2_route.default),
    ])))
  }

  lifecycle {
    create_before_destroy = true
  }
}

# Stage
resource "aws_apigatewayv2_stage" "websocket_prod" {
  api_id        = aws_apigatewayv2_api.websocket.id
  name          = "prod"
  deployment_id = aws_apigatewayv2_deployment.websocket.id

  default_route_settings {
    throttling_burst_limit = 5000
    throttling_rate_limit  = 10000
  }

  tags = {
    Name    = "eg-solo-websocket-prod-stage"
    Project = "eg-solo"
  }
}

# CloudWatch Log Group for WebSocket API Gateway
resource "aws_cloudwatch_log_group" "websocket_api_gateway" {
  name              = "/aws/apigateway/eg-solo-websocket-api"
  retention_in_days = 7

  tags = {
    Name    = "eg-solo-websocket-api-gateway-logs"
    Project = "eg-solo"
  }
}

resource "aws_iam_role" "notification_lambda_role" {
  name = "eg-solo-notification-lambda-role"

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
}

resource "aws_iam_role_policy" "notification_lambda_policy" {
  name = "notification-lambda-policy"
  role = aws_iam_role.notification_lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:Query",
          "dynamodb:GetItem",
          "dynamodb:DeleteItem"
        ]
        Resource = [
          aws_dynamodb_table.websocket_connections.arn,
          "${aws_dynamodb_table.websocket_connections.arn}/index/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "execute-api:ManageConnections"
        ]
        Resource = "arn:aws:execute-api:${var.aws_region}:*:${aws_apigatewayv2_api.websocket.id}/*"
      }
    ]
  })
}

resource "aws_lambda_function" "notification" {
  filename         = "${path.module}/lambda-notification.zip"
  function_name    = "eg-solo-websocket-notification"
  role             = aws_iam_role.notification_lambda_role.arn
  handler          = "index.handler"
  source_code_hash = filebase64sha256("${path.module}/lambda-notification.zip")
  runtime          = "nodejs18.x"
  timeout          = 30

  environment {
    variables = {
      TABLE_NAME         = aws_dynamodb_table.websocket_connections.name
      WEBSOCKET_ENDPOINT = "https://${aws_apigatewayv2_api.websocket.id}.execute-api.${var.aws_region}.amazonaws.com/${aws_apigatewayv2_stage.websocket_prod.name}"
    }
  }
}

resource "aws_cloudwatch_log_group" "notification_lambda" {
  name              = "/aws/lambda/eg-solo-websocket-notification"
  retention_in_days = 7
}

# DynamoDB table (if you don't already have one)
resource "aws_dynamodb_table" "websocket_connections" {
  name         = "eg-solo-websocket-connections"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "connectionId"

  attribute {
    name = "connectionId"
    type = "S"
  }

  attribute {
    name = "userId"
    type = "S"
  }

  global_secondary_index {
    name            = "UserIdIndex"
    hash_key        = "userId"
    projection_type = "ALL"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }
}