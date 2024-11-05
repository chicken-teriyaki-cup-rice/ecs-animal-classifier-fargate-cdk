# Real-time Animal Classifier for Mobile and Edge Devices

Scalable microservices architecture for real-time image classification using AWS ECS, ALB, and WebSockets to identify animals in images. The application consists of a FastAPI backend for WebSocket-based image processing and a Streamlit frontend for user interaction.




https://github.com/user-attachments/assets/9d135cd9-3133-4334-9cd8-c0f42023db6d



 
## Architecture

```mermaid
graph TB
    subgraph VPC
        subgraph "Private Subnets"
            BE["Backend Service<br/>(Fargate)"]
            FE["Frontend Service<br/>(Fargate)"]
        end
        
        subgraph "ECS Cluster"
            BE
            FE
        end
    end
    
    Internet((Internet))
    ECR[(ECR<br/>Repositories)]
    
    BE_ALB["Backend ALB"]
    FE_ALB["Frontend ALB"]
    
    Internet --> BE_ALB
    Internet --> FE_ALB
    
    BE_ALB --> BE
    FE_ALB --> FE
    
    BE <--> FE
    
    ECR --> BE
    ECR --> FE
    
    classDef default fill:#f9f,stroke:#333,stroke-width:2px;
    classDef alb fill:#ff9,stroke:#333,stroke-width:2px;
    classDef service fill:#9ff,stroke:#333,stroke-width:2px;
    classDef internet fill:#fff,stroke:#333,stroke-width:2px;
    
    class BE_ALB,FE_ALB alb;
    class BE,FE service;
    class Internet internet;
```

### Key Components

- **VPC**: Isolated network environment with private subnets
- **ECS Cluster**: Manages Fargate tasks for both frontend and backend services
- **Frontend Service**: Streamlit application running on port 8501
- **Backend Service**: API service running on port 8000
- **Application Load Balancers**: Separate ALBs for frontend and backend services
- **ECR Repositories**: Store Docker images for both services

### Infrastructure

The application is deployed on AWS using:

- ECS Fargate for containerized services
- Application Load Balancers for HTTPS/WebSocket traffic
- Route 53 for DNS management
- ACM for SSL/TLS certificates
- CloudWatch for logging and monitoring

### Service Communication

- Frontend service communicates with backend service via WebSocket
- Both services run in private subnets with NAT gateway for outbound internet access
- Inbound traffic is routed through Application Load Balancers

### Technical Components

- Networking stack (VPC, subnets, security groups)
- ECS Cluster with Fargate tasks
- Application Load Balancers with proper health checks
- IAM roles and policies for task execution
- CloudWatch log groups for container logs

## Prerequisites

- AWS Account with appropriate permissions
- AWS CLI configured
- Python 3.9+
- Docker installed
- AWS CDK installed
- Domain name with Route 53 hosted zone
- SSL certificate in ACM

## Repository Structure

```
├── backend
│   ├── Dockerfile
│   ├── main.py
│   └── requirements.txt
├── frontend
│   ├── Dockerfile
│   ├── app.py
│   └── requirements.txt
├── infrastructure
│   ├── README.md
│   ├── app.py
│   ├── infrastructure_stack.py
│   └── requirements.txt
└── scripts
    └── monitor-deployment.sh
```

## Deployment Instructions

1. **Set Environment Variables**

```bash
export CDK_DEFAULT_ACCOUNT=your-aws-account-id
export CDK_DEFAULT_REGION=your-aws-region
export CERTIFICATE_ARN=your-certificate-arn
```

2. **Build and Push Docker Images**

```bash
# Build backend image
docker buildx build --platform linux/amd64 -t animal-classifier-backend ./backend
docker tag animal-classifier-backend:latest $AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com/animal-classifier-backend:latest
docker push $AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com/animal-classifier-backend:latest

# Build frontend image
docker buildx build --platform linux/amd64 -t animal-classifier-frontend ./frontend
docker tag animal-classifier-frontend:latest $AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com/animal-classifier-frontend:latest
docker push $AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com/animal-classifier-frontend:latest
```

3. **Deploy Infrastructure**

```bash
cd infrastructure
pip install -r requirements.txt
cdk deploy
```

4. **Monitor Deployment**

```bash
./scripts/monitor-deployment.sh
```

## Monitoring and Debugging

### Using the Monitoring Script

The `monitor-deployment.sh` script provides real-time information about:

- Service deployment status
- Task health
- Target group status
- CloudWatch logs

### Manual Checks

```bash
# Check service status
aws ecs describe-services --cluster AnimalClassifierCluster --services BackendService

# View logs
aws logs tail /aws/ecs/backend --follow
```

## Security

- HTTPS enforced for all traffic
- WebSocket connections over WSS
- Network isolation using VPC
- Least privilege IAM roles
- Container security best practices

## Development

### Local Testing

1. Run backend:

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

2. Run frontend:

```bash
cd frontend
pip install -r requirements.txt
streamlit run app.py
```

### Making Changes

1. Update application code
2. Build and push new Docker images
3. Update infrastructure if needed
4. Deploy changes using CDK

## Troubleshooting

Common issues and solutions:

1. **WebSocket Connection Issues**
   - Check DNS propagation
   - Verify security group rules
   - Check SSL certificate validity

2. **Container Startup Issues**
   - Check CloudWatch logs
   - Verify environment variables
   - Check container health checks

3. **Deployment Issues**
   - Use monitoring script to identify problems
   - Check CloudFormation events
   - Verify IAM permissions

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes
4. Submit a pull request

## License

MIT License
