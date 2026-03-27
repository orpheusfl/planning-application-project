#!/bin/bash

# --- Configuration ---
AWS_REGION="eu-west-2"
AWS_ACCOUNT_ID="129033205317"
REPO_NAME="c22-planning-dashboard"
IMAGE_TAG="latest"

# Full ECR URI
ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

echo "Step 1: Authenticating Docker to ECR..."
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_URI

echo "Step 2: Building the Docker image..."
docker build -t $REPO_NAME .

echo "Step 3: Tagging the image for ECR..."
docker tag $REPO_NAME:latest $ECR_URI/$REPO_NAME:$IMAGE_TAG

echo "Step 4: Pushing the image to ECR..."
docker push $ECR_URI/$REPO_NAME:$IMAGE_TAG

echo "Success! Image is now at $ECR_URI/$REPO_NAME:$IMAGE_TAG"
