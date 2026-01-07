output "api_ecr_repository_url" {
  description = "ECR repository URL for API Lambda"
  value       = aws_ecr_repository.api.repository_url
}

output "api_lambda_function_name" {
  description = "API Lambda function name"
  value       = aws_lambda_function.api_handler.function_name
}
