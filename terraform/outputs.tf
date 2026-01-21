output "api_ecr_repository_url" {
  description = "ECR repository URL for API Lambda"
  value       = aws_ecr_repository.api.repository_url
}

output "api_gateway_endpoint" {
  description = "API Gateway endpoint URL"
  value       = aws_apigatewayv2_api.api.api_endpoint
}

output "api_lambda_function_name" {
  description = "API Lambda function name"
  value       = aws_lambda_function.api_handler.function_name
}

output "api_endpoint_url" {
  description = "Full API endpoint URL"
  value       = "${aws_apigatewayv2_api.api.api_endpoint}/api/v1/audio"
}

output "lambda_function_name" {
  description = "Name of the Lambda function"
  value       = aws_lambda_function.inference.function_name
}

output "lambda_function_arn" {
  description = "ARN of the Lambda function"
  value       = aws_lambda_function.inference.arn
}

output "lambda_role_arn" {
  description = "ARN of the Lambda execution role"
  value       = aws_iam_role.lambda_role.arn
}

# WebSocket API Outputs
output "websocket_url" {
  description = "WebSocket API URL - Use this to connect from client"
  value       = aws_apigatewayv2_stage.websocket_prod.invoke_url
}

output "websocket_api_id" {
  description = "WebSocket API ID"
  value       = aws_apigatewayv2_api.websocket.id
}

output "websocket_endpoint" {
  description = "WebSocket API endpoint"
  value       = aws_apigatewayv2_api.websocket.api_endpoint
}