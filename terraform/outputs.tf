output "api_ecr_repository_url" {
  description = "ECR repository URL for API Lambda"
  value       = aws_ecr_repository.api.repository_url
}