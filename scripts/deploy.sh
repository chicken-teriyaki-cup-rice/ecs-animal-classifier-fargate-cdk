#!/bin/bash

set -e
set -x

AWS_REGION="${AWS_REGION:-us-east-1}"
PLATFORM="${PLATFORM:-linux/amd64}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
BACKEND_REPO_NAME="animal-classifier-backend"
FRONTEND_REPO_NAME="animal-classifier-frontend"
BACKEND_REPO_URI="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${BACKEND_REPO_NAME}"
FRONTEND_REPO_URI="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${FRONTEND_REPO_NAME}"

CERTIFICATE_ARN="arn:aws:acm:us-east-1:225989334541:certificate/f615a168-9dd7-485f-a9e7-795733e6c6f1"

setup_ecr() {
    echo "Setting up ECR repositories..."
    aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin "${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
    for repo in $BACKEND_REPO_NAME $FRONTEND_REPO_NAME; do
        aws ecr describe-repositories --repository-names $repo --region $AWS_REGION || \
        aws ecr create-repository --repository-name $repo --region $AWS_REGION
    done
}

build_and_push_images() {
    echo "Building and pushing Docker images..."
    echo "Building backend Docker image..."
    docker build --platform=$PLATFORM -t $BACKEND_REPO_NAME ./backend
    docker tag $BACKEND_REPO_NAME:latest $BACKEND_REPO_URI:$IMAGE_TAG
    docker push $BACKEND_REPO_URI:$IMAGE_TAG

    echo "Building frontend Docker image..."
    docker build --platform=$PLATFORM -t $FRONTEND_REPO_NAME ./frontend
    docker tag $FRONTEND_REPO_NAME:latest $FRONTEND_REPO_URI:$IMAGE_TAG
    docker push $FRONTEND_REPO_URI:$IMAGE_TAG
}

deploy_infrastructure() {
    echo "Deploying AWS infrastructure with CDK..."
    cd infrastructure
    echo "{
        \"CERTIFICATE_ARN\": \"$CERTIFICATE_ARN\"
    }" > cdk.context.json
    cdk diff || true
    cdk deploy --require-approval never
    cd ..
}

cleanup_images() {
    echo "Cleaning up local Docker images..."
    docker rmi $BACKEND_REPO_NAME:latest $BACKEND_REPO_URI:$IMAGE_TAG || true
    docker rmi $FRONTEND_REPO_NAME:latest $FRONTEND_REPO_URI:$IMAGE_TAG || true
}

main() {
    echo "Starting deployment..."
    setup_ecr
    build_and_push_images
    deploy_infrastructure
    cleanup_images
    echo "Deployment completed!"
}

main
