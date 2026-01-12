# Terraform Configuration for eg-solo Lambda

This directory contains Terraform code to deploy your Lambda function from the ECR image.

## Prerequisites

1. **Docker image pushed to ECR** (run `./build_and_push.sh` in `lambda/` first)
2. **Terraform installed** (`brew install terraform` on macOS)
3. **AWS credentials** configured (via AWS SSO or IAM)
4. **S3 bucket** created for audio input and outputs

## Setup

### 1. Create terraform.tfvars

Copy the example and fill in your values:

```bash
cd /Users/soravolk/Codes/Guitar/eg-solo-app/terraform
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` and update:

- `image_uri` — from your `build_and_push.sh` output
- `s3_bucket_name` and `s3_bucket_arn` — your S3 bucket
- `aws_region` — desired AWS region
- Other optional settings (VPC, tags, etc.)

### 2. Initialize Terraform

```bash
terraform init
```

### 3. Review the plan

```bash
terraform plan
```

This shows what resources will be created.

### 4. Apply the configuration

```bash
terraform apply
```

Confirm with `yes` when prompted.

## Outputs

After `apply`, Terraform prints:

- `lambda_function_name` — your Lambda function name
- `lambda_function_arn` — Lambda ARN (for API Gateway, EventBridge, etc.)
- `lambda_role_arn` — IAM role ARN

## Next Steps

### Invoke the Lambda manually

```bash
aws lambda invoke \
  --function-name eg-solo-inference \
  --payload '{"audio_key":"20_1.wav"}' \
  response.json
```

### Add API Gateway (optional)

To expose the Lambda via HTTP, add `allow_invocation_from = "apigateway.amazonaws.com"` in `terraform.tfvars` and re-apply.

Then create an API Gateway HTTP integration manually or via Terraform.

### Add ECS task invocation (optional)

If using Fargate to invoke Lambda:

```bash
allow_invocation_from = "ecs-tasks.amazonaws.com"
```

Then your ECS task role can call:

```python
import boto3
lambda_client = boto3.client("lambda")
lambda_client.invoke(FunctionName="eg-solo-inference", InvocationType="Event", Payload=...)
```

## Tear down

To delete all resources:

```bash
terraform destroy
```

## Troubleshooting

- **"No declaration found for var.xxx"**: Make sure you've created `terraform.tfvars` from the example.
- **"ECR image not found"**: Verify `image_uri` is correct and the image was pushed to ECR.
- **Lambda execution fails**: Check CloudWatch logs and ensure the S3 bucket policy allows read/write.

## File Structure

```
terraform/
├── main.tf                    # Lambda, IAM, S3 policy
├── variables.tf               # Variable definitions
├── terraform.tfvars           # Your values (don't commit!)
├── terraform.tfvars.example   # Example template
└── README.md                  # This file
```
