variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "s3_bucket_name" {
  description = "S3 bucket name for audio input and output"
  type        = string
  default     = "solola-bucket"
}

variable "s3_bucket_arn" {
  description = "S3 bucket ARN"
  type        = string
  default     = "arn:aws:s3:::solola-bucket"
}

# API Lambda Variables
variable "api_function_name" {
  description = "API Lambda function name"
  type        = string
  default     = "eg-solo-api"
}

variable "api_image_uri" {
  description = "ECR image URI for API Lambda function"
  type        = string
  default     = "050752609443.dkr.ecr.us-east-1.amazonaws.com/eg-solo-api:latest"
}

variable "api_lambda_timeout" {
  description = "API Lambda function timeout in seconds"
  type        = number
  default     = 30
}

variable "api_lambda_memory" {
  description = "API Lambda function memory in MB"
  type        = number
  default     = 512
}

variable "cors_origins" {
  description = "Allowed CORS origins for API Gateway"
  type        = list(string)
  default     = ["http://localhost:5173", "*"]
}
