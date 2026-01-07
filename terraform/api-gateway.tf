# HTTP API Gateway
resource "aws_apigatewayv2_api" "api" {
  name          = "eg-solo-api"
  protocol_type = "HTTP"
  description   = "API Gateway for EG Solo audio upload"

  cors_configuration {
    allow_origins = var.cors_origins
    allow_methods = ["GET", "POST", "OPTIONS"]
    allow_headers = ["content-type", "authorization"]
    max_age       = 300
  }

  tags = {
    Name    = "eg-solo-api"
    Project = "eg-solo"
  }
}

# Lambda integration
resource "aws_apigatewayv2_integration" "api_lambda" {
  api_id           = aws_apigatewayv2_api.api.id
  integration_type = "AWS_PROXY"
  integration_uri  = aws_lambda_function.api_handler.invoke_arn

  payload_format_version = "2.0"
}

# Route: POST /api/v1/audio
resource "aws_apigatewayv2_route" "audio_post" {
  api_id    = aws_apigatewayv2_api.api.id
  route_key = "POST /api/v1/audio"
  target    = "integrations/${aws_apigatewayv2_integration.api_lambda.id}"
}

# Route: GET / (health check)
resource "aws_apigatewayv2_route" "root_get" {
  api_id    = aws_apigatewayv2_api.api.id
  route_key = "GET /"
  target    = "integrations/${aws_apigatewayv2_integration.api_lambda.id}"
}

# Stage (deployment environment)
resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.api.id
  name        = "$default"
  auto_deploy = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_gateway.arn
    format = jsonencode({
      requestId      = "$context.requestId"
      ip             = "$context.identity.sourceIp"
      requestTime    = "$context.requestTime"
      httpMethod     = "$context.httpMethod"
      routeKey       = "$context.routeKey"
      status         = "$context.status"
      protocol       = "$context.protocol"
      responseLength = "$context.responseLength"
    })
  }

  tags = {
    Name    = "eg-solo-api-default-stage"
    Project = "eg-solo"
  }
}

# CloudWatch Log Group for API Gateway
resource "aws_cloudwatch_log_group" "api_gateway" {
  name              = "/aws/apigateway/eg-solo-api"
  retention_in_days = 7

  tags = {
    Name    = "eg-solo-api-gateway-logs"
    Project = "eg-solo"
  }
}

# Permission for API Gateway to invoke Lambda
resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api_handler.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.api.execution_arn}/*/*"
}
