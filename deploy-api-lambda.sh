#!/bin/bash

# Script to rebuild and deploy API Lambda function
set -e  # Exit on error

# Find Docker
if command -v docker &> /dev/null; then
    DOCKER="docker"
elif [ -f "/Applications/Docker.app/Contents/Resources/bin/docker" ]; then
    DOCKER="/Applications/Docker.app/Contents/Resources/bin/docker"
else
    echo "❌ Docker not found. Please install Docker Desktop"
    exit 1
fi

cd "$(dirname "$0")/api-lambda"

echo "🔨 Building Docker image..."
$DOCKER build --platform linux/amd64 -t eg-solo-api:latest .

echo ""
echo "📋 Getting ECR repository URL..."
ECR_URL=$(aws ecr describe-repositories \
  --repository-names eg-solo-api \
  --query 'repositories[0].repositoryUri' \
  --output text \
  --profile solola-admin \
  --region us-east-1)

echo "✅ ECR URL: $ECR_URL"

echo ""
echo "🔐 Logging into ECR..."
aws ecr get-login-password \
  --region us-east-1 \
  --profile solola-admin | \
  $DOCKER login \
  --username AWS \
  --password-stdin 050752609443.dkr.ecr.us-east-1.amazonaws.com

echo ""
echo "🏷️  Tagging image..."
$DOCKER tag eg-solo-api:latest $ECR_URL:latest

echo ""
echo "⬆️  Pushing to ECR..."
$DOCKER push $ECR_URL:latest

echo ""
echo "🔄 Updating Lambda function..."
aws lambda update-function-code \
  --function-name eg-solo-api \
  --image-uri $ECR_URL:latest \
  --profile solola-admin \
  --region us-east-1

echo ""
echo "⏳ Waiting for Lambda to update..."
aws lambda wait function-updated \
  --function-name eg-solo-api \
  --profile solola-admin \
  --region us-east-1

echo ""
echo "⚙️  Updating Lambda configuration (timeout=60s)..."
aws lambda update-function-configuration \
  --function-name eg-solo-api \
  --timeout 60 \
  --profile solola-admin \
  --region us-east-1

echo ""
echo "⏳ Waiting for config update..."
aws lambda wait function-updated \
  --function-name eg-solo-api \
  --profile solola-admin \
  --region us-east-1

echo ""
echo "✅ Deployment complete!"
echo ""
echo "🧪 Test with: ./test-lambda.sh"
