#!/bin/bash
# Deploy frontend to S3 + CloudFront

set -e

PROFILE="solola-admin"
REGION="us-east-1"

# Get values from Terraform outputs
echo "🔍 Getting infrastructure details from Terraform..."
cd "$(dirname "$0")/terraform"

BUCKET_NAME=$(terraform output -raw frontend_s3_bucket 2>/dev/null || echo "")
DISTRIBUTION_ID=$(terraform output -raw cloudfront_distribution_id 2>/dev/null || echo "")
CLOUDFRONT_URL=$(terraform output -raw frontend_url 2>/dev/null || echo "")
API_ENDPOINT=$(terraform output -raw api_endpoint_url 2>/dev/null || echo "")

if [ -z "$BUCKET_NAME" ] || [ -z "$DISTRIBUTION_ID" ]; then
  echo "❌ Error: Terraform outputs not found. Please run 'terraform apply' first."
  exit 1
fi

echo "📦 S3 Bucket: $BUCKET_NAME"
echo "🌐 CloudFront Distribution: $DISTRIBUTION_ID"
echo "🔗 Frontend URL: $CLOUDFRONT_URL"
echo "🔗 API Endpoint: $API_ENDPOINT"
echo ""

# Build frontend
echo "🏗️  Building frontend..."
cd ../web

# Update .env with API endpoint if exists
if [ -n "$API_ENDPOINT" ]; then
  echo "📝 Updating .env with API endpoint..."
  cat > .env.production << EOF
VITE_API_URL=$API_ENDPOINT
EOF
  echo "✅ Created .env.production with API_URL=$API_ENDPOINT"
fi

# Build
npm run build

# Upload to S3
echo ""
echo "📤 Uploading to S3..."

# Upload all files except index.html with long cache
aws s3 sync dist/ s3://${BUCKET_NAME}/ \
  --profile $PROFILE \
  --region $REGION \
  --delete \
  --cache-control "public, max-age=31536000, immutable" \
  --exclude "index.html" \
  --exclude "*.html"

# Upload HTML files with no-cache
echo "📄 Uploading HTML files with no-cache..."
aws s3 sync dist/ s3://${BUCKET_NAME}/ \
  --profile $PROFILE \
  --region $REGION \
  --cache-control "no-cache, no-store, must-revalidate" \
  --exclude "*" \
  --include "*.html"

# Invalidate CloudFront cache
echo ""
echo "🔄 Invalidating CloudFront cache..."
INVALIDATION_ID=$(aws cloudfront create-invalidation \
  --profile $PROFILE \
  --distribution-id $DISTRIBUTION_ID \
  --paths "/*" \
  --query 'Invalidation.Id' \
  --output text)

echo "✅ Cache invalidation created: $INVALIDATION_ID"
echo ""
echo "⏳ Waiting for invalidation to complete (this may take 1-2 minutes)..."
aws cloudfront wait invalidation-completed \
  --profile $PROFILE \
  --distribution-id $DISTRIBUTION_ID \
  --id $INVALIDATION_ID

echo ""
echo "✅ Deployment complete!"
echo ""
echo "🌐 Frontend URL: $CLOUDFRONT_URL"
echo "🔗 API Endpoint: $API_ENDPOINT"
echo ""
echo "Note: It may take a few minutes for CloudFront to fully propagate."
