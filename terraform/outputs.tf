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
