# ECR Repository for API Lambda
resource "aws_ecr_repository" "api" {
  name                 = "eg-solo-api"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name        = "eg-solo-api"
    Environment = "production"
    Project     = "eg-solo"
  }
}

# ECR Lifecycle Policy to keep only the last 5 images
resource "aws_ecr_lifecycle_policy" "api" {
  repository = aws_ecr_repository.api.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep last 5 images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 5
      }
      action = {
        type = "expire"
      }
    }]
  })
}
