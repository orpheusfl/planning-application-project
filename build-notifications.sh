#!/bin/bash

# Build script for C22 Planning Notifications Lambda
# This script builds and pushes the Docker image to ECR

set -e

# Configuration
AWS_REGION=${AWS_REGION:-eu-west-2}
IMAGE_NAME="c22-planning-notifications"
DOCKERFILE_PATH="notifications/Dockerfile"

# Get AWS account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_URL="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
REPOSITORY_NAME="c22-planning-notifications"
IMAGE_TAG="${1:-latest}"

echo "=========================================="
echo "Building Notifications Lambda"
echo "=========================================="
echo "AWS Region: $AWS_REGION"
echo "ECR URL: $ECR_URL"
echo "Repository: $REPOSITORY_NAME"
echo "Image Tag: $IMAGE_TAG"
echo ""

# Build the Docker image
echo "Building Docker image..."
docker build \
  -t "${IMAGE_NAME}:${IMAGE_TAG}" \
  -t "${IMAGE_NAME}:latest" \
  -f "${DOCKERFILE_PATH}" \
  .

if [ $? -ne 0 ]; then
  echo "❌ Docker build failed"
  exit 1
fi

echo "✓ Docker build successful"
echo ""

# Login to ECR
echo "Logging in to ECR..."
aws ecr get-login-password --region "${AWS_REGION}" | \
  docker login --username AWS --password-stdin "${ECR_URL}"

if [ $? -ne 0 ]; then
  echo "❌ ECR login failed"
  exit 1
fi

echo "✓ ECR login successful"
echo ""

# Tag image with ECR URL
echo "Tagging image for ECR..."
docker tag "${IMAGE_NAME}:${IMAGE_TAG}" \
  "${ECR_URL}/${REPOSITORY_NAME}:${IMAGE_TAG}"
docker tag "${IMAGE_NAME}:latest" \
  "${ECR_URL}/${REPOSITORY_NAME}:latest"

echo "✓ Image tagged"
echo ""

# Push to ECR
echo "Pushing image to ECR..."
docker push "${ECR_URL}/${REPOSITORY_NAME}:${IMAGE_TAG}"
docker push "${ECR_URL}/${REPOSITORY_NAME}:latest"

if [ $? -ne 0 ]; then
  echo "❌ Push to ECR failed"
  exit 1
fi

echo "✓ Image pushed to ECR"
echo ""
echo "=========================================="
echo "✓ Build and push complete!"
echo "=========================================="
echo "Image URI: ${ECR_URL}/${REPOSITORY_NAME}:${IMAGE_TAG}"
echo ""
echo "To update Lambda, run:"
echo "  aws lambda update-function-code --function-name c22-planning-notifications --image-uri ${ECR_URL}/${REPOSITORY_NAME}:${IMAGE_TAG}"
