variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "function_name" {
  description = "Lambda function name"
  type        = string
  default     = "eg-solo-inference"
}

variable "image_uri" {
  description = "ECR image URI for Lambda function"
  type        = string
  default     = "050752609443.dkr.ecr.us-east-1.amazonaws.com/eg-solo-lambda:latest"
}

variable "lambda_timeout" {
  description = "Lambda function timeout in seconds"
  type        = number
  default     = 900
}

variable "lambda_memory" {
  description = "Lambda function memory in MB (max 10240, account limit may be 3008)"
  type        = number
  default     = 3008
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
  default     = ["https://d2endw6x9lawf1.cloudfront.net", "http://localhost:5173"]
}

variable "bedrock_model_id" {
  description = "Bedrock model ID for AI-powered MusicXML correction"
  type        = string
  default     = "openai.gpt-oss-20b-1:0"
}

variable "max_fix_requests_per_hour" {
  description = "Maximum AI fix requests per user per hour"
  type        = string
  default     = "20"
}

variable "max_fix_requests_per_day" {
  description = "Maximum AI fix requests per user per day"
  type        = string
  default     = "100"
}

variable "subnet_ids" {
  description = "VPC subnet IDs for Lambda (optional for VPC mode)"
  type        = list(string)
  default     = []
}

variable "security_group_ids" {
  description = "VPC security group IDs for Lambda (optional for VPC mode)"
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "Tags for all resources"
  type        = map(string)
  default = {
    Project = "eg-solo"
    Env     = "dev"
  }
}

# --------- Fargate Configuration --------- #
variable "fargate_cpu" {
  description = "Fargate task CPU units (1024 = 1 vCPU)"
  type        = number
  default     = 2048  # 2 vCPU
}

variable "fargate_memory" {
  description = "Fargate task memory in MB"
  type        = number
  default     = 8192  # 8 GB
}

variable "fargate_subnet_ids" {
  description = "Subnet IDs for Fargate tasks (must have internet access for ECR)"
  type        = list(string)
  default     = []
}

variable "fargate_security_group_ids" {
  description = "Security group IDs for Fargate tasks"
  type        = list(string)
  default     = []
}
