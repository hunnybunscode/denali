#!/bin/bash

# Pull Keycloak Operator to ECR for better control
set -e

# Auto-detect AWS configuration
echo "Auto-detecting AWS configuration..."
AWS_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=$(aws configure get region || echo "us-east-1")

echo "✅ Detected AWS Account: $AWS_ACCOUNT"
echo "✅ Detected AWS Region: $AWS_REGION"

# Configuration
OPERATOR_IMAGE="quay.io/keycloak/keycloak-operator:26.2.5"
ECR_REGISTRY="${AWS_ACCOUNT}.dkr.ecr.${AWS_REGION}.amazonaws.com"
ECR_REPOSITORY="keycloak-operator"
ECR_TAG="26.2.5"

echo "=== Keycloak Operator to ECR Script ==="

# Step 1: Pull operator image (ensure x86_64 architecture)
echo "Step 1: Pulling Keycloak operator..."
docker pull --platform linux/x86_64 $OPERATOR_IMAGE

# Step 2: Login to ECR
echo "Step 2: Login to ECR..."
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_REGISTRY

# Step 3: Create ECR repository if needed
echo "Step 3: Creating ECR repository if needed..."
aws ecr describe-repositories --repository-names $ECR_REPOSITORY --region $AWS_REGION || \
aws ecr create-repository --repository-name $ECR_REPOSITORY --region $AWS_REGION

# Step 4: Tag for ECR
echo "Step 4: Tagging operator for ECR..."
docker tag $OPERATOR_IMAGE $ECR_REGISTRY/$ECR_REPOSITORY:$ECR_TAG

# Step 5: Push to ECR
echo "Step 5: Pushing operator to ECR..."
docker push $ECR_REGISTRY/$ECR_REPOSITORY:$ECR_TAG

echo "=== Operator Migration Complete ==="
echo "Update kubernetes.yml to use: $ECR_REGISTRY/$ECR_REPOSITORY:$ECR_TAG"