# Real-time Animal Classifier for Mobile and Edge Devices

Scalable microservices architecture for real-time image classification using AWS ECS, ALB, and WebSockets to identify animals in images. The application consists of a FastAPI backend for WebSocket-based image processing and a Streamlit frontend for user interaction.



<div align="center">
  <video width="100%" max-width="800px" src="https://github.com/user-attachments/assets/9d135cd9-3133-4334-9cd8-c0f42023db6d"></video>
</div>


 
## Architecture

```mermaid
flowchart TB
    subgraph internet["Internet"]
        client(("Client"))
    end

    subgraph vpc["VPC"]
        subgraph alb["Application Load Balancers"]
            falb["Frontend ALB\nPort 80"]
            balb["Backend ALB\nPort 80"]
        end
        
        subgraph private["Private Subnets with NAT"]
            subgraph ecs["ECS Cluster"]
                subgraph frontend["Frontend Service"]
                    fe["Fargate Tasks\nStreamlit:8501"]
                end
                
                subgraph backend["Backend Service"]
                    be["Fargate Tasks\nFastAPI:8000"]
                end
            end
        end

        subgraph sg["Security Groups"]
            fsg["Frontend SG\nInbound: 8501"]
            bsg["Backend SG\nInbound: 8000"]
        end
    end

    subgraph monitoring["Monitoring"]
        logs["CloudWatch\nLogs"]
    end

    client --> falb
    client --> balb
    falb --> fe
    balb --> be
    fe --> bsg
    be --> fsg
    fe --> logs
    be --> logs
    fe <--> be

    classDef default fill:#f9f9f9,stroke:#333,stroke-width:2px
    classDef vpc fill:#e9e9e9,stroke:#666
    classDef alb fill:#FFE4B5,stroke:#d49d4f
    classDef service fill:#B0E0E6,stroke:#4682B4
    classDef security fill:#FFA07A,stroke:#FF6347
    classDef monitoring fill:#98FB98,stroke:#3CB371
    
    class vpc vpc
    class falb,balb alb
    class fe,be service
    class fsg,bsg security
    class logs monitoring
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
