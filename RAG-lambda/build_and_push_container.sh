#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# ==========================================
# CONFIGURATION VARIABLES
# ==========================================
REGION="eu-west-2"
REPO_NAME="c22-planning-rag-repo"
LAMBDA_NAME="c22-planning-rag-lambda"
IMAGE_TAG="latest"

echo "=========================================="
echo "Starting deployment for $LAMBDA_NAME"
echo "=========================================="

# 1. Get AWS Account ID dynamically
echo "[1/6] Fetching AWS Account ID..."
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
if [ -z "$ACCOUNT_ID" ]; then
    echo "Error: Failed to fetch AWS Account ID. Make sure your AWS CLI is configured."
    exit 1
fi

ECR_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"
FULL_IMAGE_URI="${ECR_URI}/${REPO_NAME}:${IMAGE_TAG}"

# 2. Authenticate Docker to AWS ECR
echo "[2/6] Authenticating Docker with ECR..."
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ECR_URI

# 3. Build the Docker Image
# Note: Ensure your Dockerfile is in the same directory you run this script from
echo "[3/6] Building the Docker image..."
docker build --provenance=false --platform linux/amd64 -t $REPO_NAME .

# 4. Tag the Image for ECR
echo "[4/6] Tagging the image..."
docker tag ${REPO_NAME}:${IMAGE_TAG} $FULL_IMAGE_URI

# 5. Push the Image to ECR
echo "[5/6] Pushing the image to ECR..."
docker push $FULL_IMAGE_URI

# 6. Update the Lambda Function
echo "[6/6] Updating Lambda function to use the new image..."
echo "Loading to function $LAMBDA_NAME, uri $FULL_IMAGE_URI, region $REGION"
aws lambda update-function-code \
    --function-name $LAMBDA_NAME \
    --image-uri $FULL_IMAGE_URI \
    --region $REGION > /dev/null # Suppressing the massive JSON output

echo "=========================================="
echo "Deployment successful! Lambda is updating."
echo "Note: It may take a few seconds for the Lambda state to become 'Active'."
echo "=========================================="