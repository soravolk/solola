# S3 bucket for audio uploads (already exists, imported into Terraform)
resource "aws_s3_bucket" "audio" {
  bucket = var.s3_bucket_name

  tags = {
    Name    = "solola-bucket"
    Project = "eg-solo"
  }
}

# CORS configuration - matches existing configuration applied via fix-s3-cors.sh
resource "aws_s3_bucket_cors_configuration" "audio" {
  bucket = aws_s3_bucket.audio.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["GET", "PUT", "POST", "DELETE", "HEAD"]
    allowed_origins = ["*"]  # In production, restrict to your CloudFront domain
    expose_headers  = ["ETag"]
    max_age_seconds = 3000
  }
}

# Server-side encryption - matches existing AES256 encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "audio" {
  bucket = aws_s3_bucket.audio.id

  rule {
    bucket_key_enabled = true
    
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Versioning - currently disabled in your bucket
resource "aws_s3_bucket_versioning" "audio" {
  bucket = aws_s3_bucket.audio.id
  
  versioning_configuration {
    status = "Disabled"  # Changed from "Enabled" to match current state
  }
}

# Block public access (optional - only add if you want this)
resource "aws_s3_bucket_public_access_block" "audio" {
  bucket = aws_s3_bucket.audio.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}