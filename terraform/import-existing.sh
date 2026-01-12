#!/bin/bash
# Import existing AWS resources into Terraform state

set -e

PROFILE="solola-admin"
REGION="us-east-1"
ACCOUNT_ID=$(aws sts get-caller-identity --profile $PROFILE --query Account --output text)

echo "🔍 Importing existing AWS resources into Terraform..."
echo "Account ID: $ACCOUNT_ID"
echo ""

# =============================================================================
# API LAMBDA RESOURCES (eg-solo-api)
# =============================================================================
echo "📦 Importing API Lambda resources..."

# ECR repository
echo "  - ECR repository: eg-solo-api"
terraform import aws_ecr_repository.api eg-solo-api 2>/dev/null || echo "    ⚠️  Already imported or not found"

# ECR lifecycle policy
echo "  - ECR lifecycle policy"
terraform import aws_ecr_lifecycle_policy.api eg-solo-api 2>/dev/null || echo "    ⚠️  Already imported or not found"

# IAM role
echo "  - IAM role: eg-solo-api-lambda-role"
terraform import aws_iam_role.api_lambda_role eg-solo-api-lambda-role 2>/dev/null || echo "    ⚠️  Already imported or not found"

# IAM role policy attachment
echo "  - IAM role policy attachment (Basic Execution)"
terraform import aws_iam_role_policy_attachment.api_lambda_basic eg-solo-api-lambda-role/arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole 2>/dev/null || echo "    ⚠️  Already imported or not found"

# IAM inline policy
echo "  - IAM inline policy (S3 access)"
terraform import aws_iam_role_policy.api_lambda_s3 eg-solo-api-lambda-role:s3-presigned-url-access 2>/dev/null || echo "    ⚠️  Already imported or not found"

# Lambda function
echo "  - Lambda function: eg-solo-api"
terraform import aws_lambda_function.api_handler eg-solo-api 2>/dev/null || echo "    ⚠️  Already imported or not found"

# CloudWatch log group
echo "  - CloudWatch log group: /aws/lambda/eg-solo-api"
terraform import aws_cloudwatch_log_group.api_lambda /aws/lambda/eg-solo-api 2>/dev/null || echo "    ⚠️  Already imported or not found"

# =============================================================================
# API GATEWAY RESOURCES
# =============================================================================
echo ""
echo "🌐 Importing API Gateway resources..."

API_ID=$(aws apigatewayv2 get-apis --profile $PROFILE --region $REGION --query "Items[?Name=='eg-solo-api'].ApiId" --output text 2>/dev/null)
if [ -n "$API_ID" ] && [ "$API_ID" != "None" ]; then
  echo "  Found API Gateway ID: $API_ID"
  
  # API Gateway
  echo "  - API Gateway: eg-solo-api"
  terraform import aws_apigatewayv2_api.api $API_ID 2>/dev/null || echo "    ⚠️  Already imported"
  
  # Stage
  echo "  - Stage: \$default"
  terraform import aws_apigatewayv2_stage.default $API_ID/\$default 2>/dev/null || echo "    ⚠️  Already imported"
  
  # Integration
  INTEGRATION_ID=$(aws apigatewayv2 get-integrations --api-id $API_ID --profile $PROFILE --region $REGION --query "Items[0].IntegrationId" --output text 2>/dev/null)
  if [ -n "$INTEGRATION_ID" ] && [ "$INTEGRATION_ID" != "None" ]; then
    echo "  - Integration: $INTEGRATION_ID"
    terraform import aws_apigatewayv2_integration.api_lambda $API_ID/$INTEGRATION_ID 2>/dev/null || echo "    ⚠️  Already imported"
  fi
  
  # Routes
  POST_ROUTE_ID=$(aws apigatewayv2 get-routes --api-id $API_ID --profile $PROFILE --region $REGION --query "Items[?RouteKey=='POST /api/v1/audio'].RouteId" --output text 2>/dev/null)
  if [ -n "$POST_ROUTE_ID" ] && [ "$POST_ROUTE_ID" != "None" ]; then
    echo "  - Route: POST /api/v1/audio"
    terraform import aws_apigatewayv2_route.audio_post $API_ID/$POST_ROUTE_ID 2>/dev/null || echo "    ⚠️  Already imported"
  fi
  
  GET_ROUTE_ID=$(aws apigatewayv2 get-routes --api-id $API_ID --profile $PROFILE --region $REGION --query "Items[?RouteKey=='GET /'].RouteId" --output text 2>/dev/null)
  if [ -n "$GET_ROUTE_ID" ] && [ "$GET_ROUTE_ID" != "None" ]; then
    echo "  - Route: GET /"
    terraform import aws_apigatewayv2_route.root_get $API_ID/$GET_ROUTE_ID 2>/dev/null || echo "    ⚠️  Already imported"
  fi
  
  # CloudWatch log group
  echo "  - CloudWatch log group: /aws/apigateway/eg-solo-api"
  terraform import aws_cloudwatch_log_group.api_gateway /aws/apigateway/eg-solo-api 2>/dev/null || echo "    ⚠️  Already imported or not found"
  
  # Lambda permission
  echo "  - Lambda permission for API Gateway"
  terraform import aws_lambda_permission.api_gateway eg-solo-api/AllowAPIGatewayInvoke 2>/dev/null || echo "    ⚠️  Already imported or not found"
else
  echo "  ⚠️  API Gateway 'eg-solo-api' not found"
fi

# =============================================================================
# INFERENCE LAMBDA RESOURCES (eg-solo-inference)
# =============================================================================
echo ""
echo "🤖 Importing Inference Lambda resources..."

# IAM role
echo "  - IAM role: eg-solo-inference-role"
terraform import aws_iam_role.lambda_role eg-solo-inference-role 2>/dev/null || echo "    ⚠️  Already imported or not found"

# IAM role policy attachment
echo "  - IAM role policy attachment (Basic Execution)"
terraform import aws_iam_role_policy_attachment.lambda_basic_execution eg-solo-inference-role/arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole 2>/dev/null || echo "    ⚠️  Already imported or not found"

# IAM inline policies
echo "  - IAM inline policy (S3 access)"
terraform import aws_iam_role_policy.lambda_s3_policy eg-solo-inference-role:eg-solo-inference-s3-policy 2>/dev/null || echo "    ⚠️  Already imported or not found"

echo "  - IAM inline policy (ECS access)"
terraform import aws_iam_role_policy.lambda_ecs_policy eg-solo-inference-role:eg-solo-inference-lambda-ecs-policy 2>/dev/null || echo "    ⚠️  Already imported or not found"

# Lambda function
echo "  - Lambda function: eg-solo-inference"
terraform import aws_lambda_function.inference eg-solo-inference 2>/dev/null || echo "    ⚠️  Already imported or not found"

# =============================================================================
# ECS FARGATE RESOURCES
# =============================================================================
echo ""
echo "🚀 Importing ECS Fargate resources..."

# ECS Cluster
CLUSTER_ARN=$(aws ecs describe-clusters --clusters eg-solo-inference-cluster --profile $PROFILE --region $REGION --query "clusters[0].clusterArn" --output text 2>/dev/null)
if [ -n "$CLUSTER_ARN" ] && [ "$CLUSTER_ARN" != "None" ]; then
  echo "  - ECS Cluster: eg-solo-inference-cluster"
  terraform import aws_ecs_cluster.inference eg-solo-inference-cluster 2>/dev/null || echo "    ⚠️  Already imported"
fi

# CloudWatch log group
echo "  - CloudWatch log group: /ecs/eg-solo-inference"
terraform import aws_cloudwatch_log_group.fargate /ecs/eg-solo-inference 2>/dev/null || echo "    ⚠️  Already imported or not found"

# ECS Task Execution Role
echo "  - IAM role: eg-solo-inference-ecs-execution-role"
terraform import aws_iam_role.ecs_task_execution eg-solo-inference-ecs-execution-role 2>/dev/null || echo "    ⚠️  Already imported or not found"

echo "  - IAM role policy attachment (ECS Task Execution)"
terraform import aws_iam_role_policy_attachment.ecs_task_execution eg-solo-inference-ecs-execution-role/arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy 2>/dev/null || echo "    ⚠️  Already imported or not found"

# ECS Task Role
echo "  - IAM role: eg-solo-inference-ecs-task-role"
terraform import aws_iam_role.ecs_task eg-solo-inference-ecs-task-role 2>/dev/null || echo "    ⚠️  Already imported or not found"

echo "  - IAM inline policy (ECS Task S3 access)"
terraform import aws_iam_role_policy.ecs_task_s3 eg-solo-inference-ecs-task-role:eg-solo-inference-ecs-task-s3-policy 2>/dev/null || echo "    ⚠️  Already imported or not found"

# ECS Task Definition
TASK_DEF_ARN=$(aws ecs describe-task-definition --task-definition eg-solo-inference-task --profile $PROFILE --region $REGION --query "taskDefinition.taskDefinitionArn" --output text 2>/dev/null)
if [ -n "$TASK_DEF_ARN" ] && [ "$TASK_DEF_ARN" != "None" ]; then
  echo "  - ECS Task Definition: eg-solo-inference-task"
  terraform import aws_ecs_task_definition.inference $TASK_DEF_ARN 2>/dev/null || echo "    ⚠️  Already imported"
fi

# =============================================================================
# VPC RESOURCES
# =============================================================================
echo ""
echo "🌍 Importing VPC resources..."

# VPC
VPC_ID=$(aws ec2 describe-vpcs --filters "Name=tag:Name,Values=eg-solo-inference-vpc" --profile $PROFILE --region $REGION --query "Vpcs[0].VpcId" --output text 2>/dev/null)
if [ -n "$VPC_ID" ] && [ "$VPC_ID" != "None" ]; then
  echo "  Found VPC ID: $VPC_ID"
  echo "  - VPC: eg-solo-inference-vpc"
  terraform import aws_vpc.main $VPC_ID 2>/dev/null || echo "    ⚠️  Already imported"
  
  # Internet Gateway
  IGW_ID=$(aws ec2 describe-internet-gateways --filters "Name=attachment.vpc-id,Values=$VPC_ID" --profile $PROFILE --region $REGION --query "InternetGateways[0].InternetGatewayId" --output text 2>/dev/null)
  if [ -n "$IGW_ID" ] && [ "$IGW_ID" != "None" ]; then
    echo "  - Internet Gateway: $IGW_ID"
    terraform import aws_internet_gateway.main $IGW_ID 2>/dev/null || echo "    ⚠️  Already imported"
  fi
  
  # Subnets
  SUBNET_1_ID=$(aws ec2 describe-subnets --filters "Name=tag:Name,Values=eg-solo-inference-public-1" --profile $PROFILE --region $REGION --query "Subnets[0].SubnetId" --output text 2>/dev/null)
  if [ -n "$SUBNET_1_ID" ] && [ "$SUBNET_1_ID" != "None" ]; then
    echo "  - Subnet: eg-solo-inference-public-1"
    terraform import aws_subnet.public_1 $SUBNET_1_ID 2>/dev/null || echo "    ⚠️  Already imported"
  fi
  
  SUBNET_2_ID=$(aws ec2 describe-subnets --filters "Name=tag:Name,Values=eg-solo-inference-public-2" --profile $PROFILE --region $REGION --query "Subnets[0].SubnetId" --output text 2>/dev/null)
  if [ -n "$SUBNET_2_ID" ] && [ "$SUBNET_2_ID" != "None" ]; then
    echo "  - Subnet: eg-solo-inference-public-2"
    terraform import aws_subnet.public_2 $SUBNET_2_ID 2>/dev/null || echo "    ⚠️  Already imported"
  fi
  
  # Route Table
  RT_ID=$(aws ec2 describe-route-tables --filters "Name=tag:Name,Values=eg-solo-inference-public-rt" --profile $PROFILE --region $REGION --query "RouteTables[0].RouteTableId" --output text 2>/dev/null)
  if [ -n "$RT_ID" ] && [ "$RT_ID" != "None" ]; then
    echo "  - Route Table: eg-solo-inference-public-rt"
    terraform import aws_route_table.public $RT_ID 2>/dev/null || echo "    ⚠️  Already imported"
    
    # Route Table Associations
    if [ -n "$SUBNET_1_ID" ] && [ "$SUBNET_1_ID" != "None" ]; then
      ASSOC_1_ID=$(aws ec2 describe-route-tables --route-table-ids $RT_ID --profile $PROFILE --region $REGION --query "RouteTables[0].Associations[?SubnetId=='$SUBNET_1_ID'].RouteTableAssociationId" --output text 2>/dev/null)
      if [ -n "$ASSOC_1_ID" ] && [ "$ASSOC_1_ID" != "None" ]; then
        echo "  - Route Table Association: public-1"
        terraform import aws_route_table_association.public_1 $ASSOC_1_ID 2>/dev/null || echo "    ⚠️  Already imported"
      fi
    fi
    
    if [ -n "$SUBNET_2_ID" ] && [ "$SUBNET_2_ID" != "None" ]; then
      ASSOC_2_ID=$(aws ec2 describe-route-tables --route-table-ids $RT_ID --profile $PROFILE --region $REGION --query "RouteTables[0].Associations[?SubnetId=='$SUBNET_2_ID'].RouteTableAssociationId" --output text 2>/dev/null)
      if [ -n "$ASSOC_2_ID" ] && [ "$ASSOC_2_ID" != "None" ]; then
        echo "  - Route Table Association: public-2"
        terraform import aws_route_table_association.public_2 $ASSOC_2_ID 2>/dev/null || echo "    ⚠️  Already imported"
      fi
    fi
  fi
  
  # Security Group
  SG_ID=$(aws ec2 describe-security-groups --filters "Name=tag:Name,Values=eg-solo-inference-fargate-sg" --profile $PROFILE --region $REGION --query "SecurityGroups[0].GroupId" --output text 2>/dev/null)
  if [ -n "$SG_ID" ] && [ "$SG_ID" != "None" ]; then
    echo "  - Security Group: eg-solo-inference-fargate-sg"
    terraform import aws_security_group.fargate $SG_ID 2>/dev/null || echo "    ⚠️  Already imported"
  fi
else
  echo "  ⚠️  VPC 'eg-solo-inference-vpc' not found"
fi

echo ""
echo "✅ Import complete! Run 'terraform plan' to verify."
echo ""
echo "Next steps:"
echo "  1. terraform plan   # Check for any differences"
echo "  2. terraform apply  # Apply any necessary updates"
