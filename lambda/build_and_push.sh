#!/bin/bash
# Build and push Lambda Docker image to ECR
# Usage: ./build_and_push.sh [region] [function-name] [aws-profile]
# Defaults: region=us-east-1, function-name=eg-solo-inference, aws-profile=(default)

set -e

REGION=${1:-us-east-1}
FUNCTION_NAME=${2:-eg-solo-inference}
AWS_PROFILE=${3:-solola-admin}  # AWS SSO profile

# Export AWS_PROFILE for all aws CLI calls
export AWS_PROFILE
echo "Using AWS profile: $AWS_PROFILE"
IMAGE_NAME="eg-solo-lambda"
REPO_NAME="eg-solo-lambda"

# Get AWS account ID
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_URI="$AWS_ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com"
IMAGE_URI="$ECR_URI/$REPO_NAME:latest"

echo "=========================================="
echo "Build & Push Lambda Image to ECR"
echo "=========================================="
echo "Region: $REGION"
echo "Account: $AWS_ACCOUNT_ID"
echo "ECR URI: $IMAGE_URI"
echo ""

# Create ECR repo if it doesn't exist
echo "[1/4] Creating ECR repository (if needed)..."
aws ecr create-repository \
  --repository-name $REPO_NAME \
  --region $REGION \
  2>/dev/null || echo "  Repository already exists"
echo ""

# Login Docker to ECR
echo "[2/4] Logging Docker into ECR..."
aws ecr get-login-password --region $REGION | \
  docker login --username AWS --password-stdin $ECR_URI > /dev/null
echo "  Docker login successful"
echo ""

# Build image
echo "[3/4] Building Docker image..."
docker build -t $IMAGE_NAME:latest .
echo "  Build complete"
echo ""

# Tag and push
echo "[4/4] Tagging and pushing to ECR..."
docker tag $IMAGE_NAME:latest $IMAGE_URI
docker push $IMAGE_URI
echo "  Push complete"
echo ""

echo "=========================================="
echo "✓ Image ready at: $IMAGE_URI"
echo ""
echo "To create/update Lambda function, run:"
echo "  aws lambda create-function \\"
echo "    --function-name $FUNCTION_NAME \\"
echo "    --package-type Image \\"
echo "    --code ImageUri=$IMAGE_URI \\"
echo "    --role arn:aws:iam::$AWS_ACCOUNT_ID:role/<lambda-execution-role> \\"
echo "    --timeout 900 \\"
echo "    --memory-size 2048 \\"
echo "    --region $REGION"
echo ""
echo "Or update existing:"
echo "  aws lambda update-function-code \\"
echo "    --function-name $FUNCTION_NAME \\"
echo "    --image-uri $IMAGE_URI \\"
echo "    --region $REGION"
echo "=========================================="
