#!/bin/bash

# Exit on error and print each command
set -e
set -x

# Variables with support for environment overrides
AWS_REGION="${AWS_REGION:-us-east-1}"
PLATFORM="${PLATFORM:-linux/amd64}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

BACKEND_REPO_NAME="animal-classifier-backend"
FRONTEND_REPO_NAME="animal-classifier-frontend"
BACKEND_REPO_URI="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${BACKEND_REPO_NAME}"
FRONTEND_REPO_URI="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${FRONTEND_REPO_NAME}"

echo "Starting deployment of Animal Classifier..."

# Validate AWS CLI
if ! command -v aws &> /dev/null; then
    echo "AWS CLI is not installed. Please install it and configure credentials."
    exit 1
fi

# Validate Docker
if ! command -v docker &> /dev/null; then
    echo "Docker is not installed. Please install it."
    exit 1
fi

# Validate CDK
if ! command -v cdk &> /dev/null; then
    echo "AWS CDK is not installed. Please install it by running 'npm install -g aws-cdk'."
    exit 1
fi

# Log in to Amazon ECR
echo "Logging in to Amazon ECR in region ${AWS_REGION}..."
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin "${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

# Create ECR repositories if they don't exist
echo "Creating ECR repositories if they don't exist..."
aws ecr create-repository --repository-name $BACKEND_REPO_NAME --region $AWS_REGION || true
aws ecr create-repository --repository-name $FRONTEND_REPO_NAME --region $AWS_REGION || true

# Build and push backend Docker image
echo "Building backend Docker image..."
docker build --platform=$PLATFORM -t $BACKEND_REPO_NAME ./backend

echo "Tagging backend image with ${IMAGE_TAG}..."
docker tag $BACKEND_REPO_NAME:latest $BACKEND_REPO_URI:$IMAGE_TAG

echo "Pushing backend image to ECR..."
docker push $BACKEND_REPO_URI:$IMAGE_TAG

# Build and push frontend Docker image
echo "Building frontend Docker image..."
docker build --platform=$PLATFORM -t $FRONTEND_REPO_NAME ./frontend

echo "Tagging frontend image with ${IMAGE_TAG}..."
docker tag $FRONTEND_REPO_NAME:latest $FRONTEND_REPO_URI:$IMAGE_TAG

echo "Pushing frontend image to ECR..."
docker push $FRONTEND_REPO_URI:$IMAGE_TAG

# Deploy AWS infrastructure with CDK
echo "Deploying AWS infrastructure with CDK..."
cd infrastructure
cdk deploy --require-approval never

# Cleanup local Docker images
echo "Cleaning up local Docker images..."
docker rmi $BACKEND_REPO_NAME:latest || echo "Backend image cleanup failed"
docker rmi $BACKEND_REPO_URI:$IMAGE_TAG || echo "Tagged backend image cleanup failed"
docker rmi $FRONTEND_REPO_NAME:latest || echo "Frontend image cleanup failed"
docker rmi $FRONTEND_REPO_URI:$IMAGE_TAG || echo "Tagged frontend image cleanup failed"

echo "Deployment complete!"
