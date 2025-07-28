#!/bin/bash

# Script to pull Ironbank Keycloak FIPS image and push to ECR
# Requires CAC authentication to registry1.dso.mil
# Auto-detects AWS account and region

set -e

# Auto-detect AWS configuration
echo "Auto-detecting AWS configuration..."
AWS_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=$(aws configure get region || echo "us-east-1")

if [ -z "$AWS_ACCOUNT" ]; then
    echo "❌ ERROR: Could not detect AWS account. Ensure AWS credentials are configured."
    exit 1
fi

echo "✅ Detected AWS Account: $AWS_ACCOUNT"
echo "✅ Detected AWS Region: $AWS_REGION"

# Configuration
IRONBANK_IMAGE="registry1.dso.mil/ironbank/opensource/keycloak/keycloak-fips:26.3.1-fips"
ECR_REGISTRY="${AWS_ACCOUNT}.dkr.ecr.${AWS_REGION}.amazonaws.com"
ECR_REPOSITORY="keycloak-fips"
ECR_TAG="26.3.1-fips"

echo "=== Ironbank to ECR Migration Script ==="

# Step 1: Login to Ironbank registry (requires CAC)
echo "Step 1: Login to Ironbank registry..."
echo "Please ensure your CAC is connected and certificates are configured"
docker login registry1.dso.mil

# Step 2: Pull Ironbank image (ensure x86_64 architecture)
echo "Step 2: Pulling Ironbank image..."
docker pull --platform linux/x86_64 $IRONBANK_IMAGE

# Step 3: Login to ECR
echo "Step 3: Login to ECR..."
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_REGISTRY

# Step 4: Create ECR repository if it doesn't exist
echo "Step 4: Creating ECR repository if needed..."
aws ecr describe-repositories --repository-names $ECR_REPOSITORY --region $AWS_REGION || \
aws ecr create-repository --repository-name $ECR_REPOSITORY --region $AWS_REGION

# Step 5: Tag image for ECR
echo "Step 5: Tagging image for ECR..."
docker tag $IRONBANK_IMAGE $ECR_REGISTRY/$ECR_REPOSITORY:$ECR_TAG

# Step 6: Push to ECR
echo "Step 6: Pushing to ECR..."
docker push $ECR_REGISTRY/$ECR_REPOSITORY:$ECR_TAG

echo "=== Migration Complete ==="
echo "Update your Kubernetes manifests to use: $ECR_REGISTRY/$ECR_REPOSITORY:$ECR_TAG"