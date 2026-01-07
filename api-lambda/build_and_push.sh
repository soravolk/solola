#!/bin/bash

# Usage: ./build_and_push.sh <region> <repository-name> <aws-profile>
# Example: ./build_and_push.sh us-east-1 eg-solo-api solola-admin

set -e

REGION=${1:-us-east-1}
REPO_NAME=${2:-eg-solo-api}
AWS_PROFILE=${3:-solola-admin}

echo "🔍 Getting AWS account ID..."
ACCOUNT_ID=$(aws sts get-caller-identity --profile $AWS_PROFILE --query Account --output text)

echo "📦 Building Docker image..."
docker build --platform linux/amd64 -t $REPO_NAME:latest .

echo "🏷️  Tagging image..."
docker tag $REPO_NAME:latest $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$REPO_NAME:latest

echo "🔐 Logging in to ECR..."
aws ecr get-login-password --region $REGION --profile $AWS_PROFILE | \
    docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com

echo "📤 Pushing image to ECR..."
docker push $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$REPO_NAME:latest

echo "✅ Done! Image pushed to: $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$REPO_NAME:latest"
