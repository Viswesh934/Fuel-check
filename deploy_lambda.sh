#!/usr/bin/env bash
# ==============================================================================
# One-Click AWS Lambda Deploy Script for Fuel Check & Disha Voice Co-Pilot
# Deploys as a Container Image on AWS Lambda with a Free Public Function URL
# ==============================================================================
set -e

REGION="${AWS_REGION:-ap-south-1}"
FUNCTION_NAME="fuel-check-copilot"
ECR_REPO_NAME="fuel-check-copilot"

echo "🚀 Deploying Fuel Check to AWS Lambda ($REGION)..."

# 1. Verify AWS CLI
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI is not installed. Please run: curl \"https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip\" -o \"awscliv2.zip\" && unzip -q awscliv2.zip && sudo ./aws/install"
    exit 1
fi

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_URI="$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$ECR_REPO_NAME"

echo "📦 Target ECR Repository: $ECR_URI"

# 2. Ensure ECR Repo exists
aws ecr describe-repositories --repository-names "$ECR_REPO_NAME" --region "$REGION" &> /dev/null || \
aws ecr create-repository --repository-name "$ECR_REPO_NAME" --region "$REGION" > /dev/null

# 3. Log in to Amazon ECR
aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com"

# 4. Build and Push Docker Image (linux/amd64 architecture for Lambda)
echo "🔨 Building Docker image (linux/amd64)..."
docker build --platform linux/amd64 -t "$ECR_REPO_NAME:latest" .
docker tag "$ECR_REPO_NAME:latest" "$ECR_URI:latest"

echo "⬆️ Pushing image to Amazon ECR..."
docker push "$ECR_URI:latest"

# 5. Create or Get IAM Role
ROLE_NAME="lambda-basic-execution-fuelcheck"
ROLE_ARN=$(aws iam get-role --role-name "$ROLE_NAME" --query "Role.Arn" --output text 2>/dev/null || true)
if [ -z "$ROLE_ARN" ]; then
    echo "🔑 Creating IAM Role for Lambda..."
    aws iam create-role --role-name "$ROLE_NAME" \
        --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}' > /dev/null
    aws iam attach-role-policy --role-name "$ROLE_NAME" \
        --policy-arn "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
    echo "⏳ Waiting for IAM role propagation..."
    sleep 10
    ROLE_ARN=$(aws iam get-role --role-name "$ROLE_NAME" --query "Role.Arn" --output text)
fi

# 6. Create or Update Lambda Function
echo "⚡ Checking Lambda Function ($FUNCTION_NAME)..."
if aws lambda get-function --function-name "$FUNCTION_NAME" --region "$REGION" &> /dev/null; then
    echo "🔄 Updating existing Lambda function code..."
    aws lambda update-function-code \
        --function-name "$FUNCTION_NAME" \
        --image-uri "$ECR_URI:latest" \
        --region "$REGION" > /dev/null
else
    echo "✨ Creating new Lambda function ($FUNCTION_NAME)..."
    aws lambda create-function \
        --function-name "$FUNCTION_NAME" \
        --package-type Image \
        --code ImageUri="$ECR_URI:latest" \
        --role "$ROLE_ARN" \
        --timeout 120 \
        --memory-size 1024 \
        --region "$REGION" > /dev/null
fi

# 7. Configure Environment Variables
echo "🔧 Configuring Environment Variables from local environment / .env..."
# Source .env if present
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

aws lambda update-function-configuration \
    --function-name "$FUNCTION_NAME" \
    --timeout 120 \
    --memory-size 1024 \
    --environment "Variables={SARVAM_API_KEY=\"${SARVAM_API_KEY}\",BOLNA_API_KEY=\"${BOLNA_API_KEY}\",BOLNA_AGENT_ID=\"${BOLNA_AGENT_ID}\",AWS_LOCATION_API_KEY=\"${AWS_LOCATION_API_KEY}\",AWS_LOCATION_REGION=\"${AWS_LOCATION_REGION:-ap-south-1}\",DJANGO_DEBUG=\"False\",IS_LAMBDA=\"true\"}" \
    --region "$REGION" > /dev/null

# 8. Ensure Function URL (Public Direct HTTPS Endpoint with zero API Gateway)
echo "🌐 Configuring Public Function URL..."
URL=$(aws lambda get-function-url-config --function-name "$FUNCTION_NAME" --region "$REGION" --query "FunctionUrl" --output text 2>/dev/null || true)
if [ -z "$URL" ]; then
    URL=$(aws lambda create-function-url-config \
        --function-name "$FUNCTION_NAME" \
        --auth-type NONE \
        --cors '{"AllowOrigins":["*"],"AllowMethods":["*"],"AllowHeaders":["*"]}' \
        --region "$REGION" \
        --query "FunctionUrl" --output text)
    aws lambda add-permission \
        --function-name "$FUNCTION_NAME" \
        --statement-id "FunctionURLAllowPublicAccess" \
        --action "lambda:InvokeFunctionUrl" \
        --principal "*" \
        --function-url-auth-type NONE \
        --region "$REGION" > /dev/null
fi

echo ""
echo "=========================================================================="
echo "✅ DEPLOYMENT SUCCESSFUL!"
echo "🌐 Live Public URL: $URL"
echo "👉 Both the Frontend Cockpit & Backend APIs are running in a single place."
echo "=========================================================================="
