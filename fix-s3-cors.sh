#!/bin/bash

# Fix S3 CORS configuration for solola-bucket
# This script applies CORS rules to allow browser uploads via presigned URLs

BUCKET_NAME="solola-bucket"
AWS_PROFILE="solola-admin"

echo "🔧 Fixing CORS configuration for S3 bucket: $BUCKET_NAME"
echo ""

# Create CORS configuration JSON
cat > /tmp/cors-config.json << 'EOF'
{
  "CORSRules": [
    {
      "AllowedHeaders": ["*"],
      "AllowedMethods": ["GET", "PUT", "POST", "DELETE", "HEAD"],
      "AllowedOrigins": ["*"],
      "ExposeHeaders": ["ETag"],
      "MaxAgeSeconds": 3000
    }
  ]
}
EOF

echo "📄 CORS Configuration:"
cat /tmp/cors-config.json
echo ""

# Apply CORS configuration
echo "🚀 Applying CORS configuration..."
aws s3api put-bucket-cors \
  --bucket "$BUCKET_NAME" \
  --cors-configuration file:///tmp/cors-config.json \
  --profile "$AWS_PROFILE"

if [ $? -eq 0 ]; then
  echo ""
  echo "✅ CORS configuration applied successfully!"
  echo ""
  echo "📋 Verifying configuration..."
  aws s3api get-bucket-cors --bucket "$BUCKET_NAME" --profile "$AWS_PROFILE"
  echo ""
  echo "🎉 Done! Your S3 bucket now accepts uploads from the browser."
else
  echo ""
  echo "❌ Failed to apply CORS configuration"
  echo "Please check:"
  echo "  1. AWS CLI is installed"
  echo "  2. Profile '$AWS_PROFILE' exists and has permissions"
  echo "  3. Bucket '$BUCKET_NAME' exists"
fi

# Clean up
rm -f /tmp/cors-config.json
