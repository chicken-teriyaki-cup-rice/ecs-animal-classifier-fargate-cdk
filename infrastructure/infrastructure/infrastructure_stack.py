import boto3
from aws_cdk import (
    CfnOutput,
    Duration,
    Stack,
    Tags,
)
from aws_cdk import (
    aws_certificatemanager as acm,
)
from aws_cdk import (
    aws_ec2 as ec2,
)
from aws_cdk import (
    aws_ecr as ecr,
)
from aws_cdk import (
    aws_ecs as ecs,
)
from aws_cdk import (
    aws_ecs_patterns as ecs_patterns,
)
from aws_cdk import (
    aws_elasticloadbalancingv2 as elbv2,
)
from aws_cdk import (
    aws_logs as logs,
)
from aws_cdk import (
    aws_route53 as route53,
)
from aws_cdk import (
    aws_route53_targets as targets,
)
from constructs import Construct


class AnimalClassifierStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Add stack-level tags
        Tags.of(self).add("Environment", "Production")
        Tags.of(self).add("Project", "AnimalClassifier")
        Tags.of(self).add("ManagedBy", "CDK")

        # AWS account and region
        account_id = Stack.of(self).account
        region = Stack.of(self).region
        domain_name = "isthisasquirrel.com"
        backend_domain = f"backend.{domain_name}"
        frontend_domain = f"frontend.{domain_name}"

        # Reference Existing ECR Repositories
        backend_repo = ecr.Repository.from_repository_name(
            self, "BackendRepo", "animal-classifier-backend"
        )
        frontend_repo = ecr.Repository.from_repository_name(
            self, "FrontendRepo", "animal-classifier-frontend"
        )

        # Create VPC with custom CIDR
        vpc = ec2.Vpc(
            self,
            "AnimalClassifierVPC",
            ip_addresses=ec2.IpAddresses.cidr("172.16.0.0/16"),
            max_azs=2,
            nat_gateways=1,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                ),
                ec2.SubnetConfiguration(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24,
                ),
            ],
        )

        # Create ECS Cluster
        cluster = ecs.Cluster(
            self,
            "AnimalClassifierCluster",
            vpc=vpc,
            container_insights=True,
        )

        # Load SSL Certificate
        certificate_arn = self.node.try_get_context("CERTIFICATE_ARN")
        if not certificate_arn:
            raise ValueError("CERTIFICATE_ARN context variable is required")

        certificate = acm.Certificate.from_certificate_arn(
            self, "AnimalClassifierCertificate", certificate_arn
        )

        # Define runtime platform for x86_64
        runtime_platform = ecs.RuntimePlatform(
            operating_system_family=ecs.OperatingSystemFamily.LINUX,
            cpu_architecture=ecs.CpuArchitecture.X86_64,
        )

        # Create Log Groups
        backend_log_group = logs.LogGroup(
            self,
            "BackendLogGroup",
            retention=logs.RetentionDays.ONE_WEEK,
        )

        frontend_log_group = logs.LogGroup(
            self,
            "FrontendLogGroup",
            retention=logs.RetentionDays.ONE_WEEK,
        )

        # Backend Service with Health Check Configuration
        # Backend Service with Health Check Configuration
        backend_service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self,
            "BackendService",
            cluster=cluster,
            cpu=1024,
            memory_limit_mib=2048,
            runtime_platform=runtime_platform,
            task_image_options=ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
                image=ecs.ContainerImage.from_ecr_repository(
                    backend_repo, tag="latest"
                ),
                container_port=8000,
                container_name="web",
                environment={
                    "PYTHONUNBUFFERED": "1",
                    "IMAGE_VERSION": "v3.3",
                    "WS_PING_INTERVAL": "20",
                    "WS_PING_TIMEOUT": "20",
                    "ALLOWED_ORIGINS": f"https://{domain_name},https://frontend.{domain_name},http://localhost:8501",
                },
                log_driver=ecs.LogDrivers.aws_logs(
                    log_group=backend_log_group,
                    stream_prefix="backend",
                ),
            ),
            public_load_balancer=True,
            desired_count=1,
            certificate=certificate,
            protocol=elbv2.ApplicationProtocol.HTTPS,
            listener_port=443,
            target_protocol=elbv2.ApplicationProtocol.HTTP,
            idle_timeout=Duration.seconds(300)
        )

        # Add container healthcheck
        backend_service.task_definition.default_container.health_check = ecs.HealthCheck(
            command=["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"],
            interval=Duration.seconds(30),
            timeout=Duration.seconds(5),
            retries=3,
            start_period=Duration.seconds(60)
        )

        # Configure ALB health check
       # In your infrastructure_stack.py
        backend_service.target_group.configure_health_check(
            path="/health",
            healthy_http_codes="200",
            interval=Duration.seconds(30),
            timeout=Duration.seconds(5),
            healthy_threshold_count=2,
            unhealthy_threshold_count=3,
            protocol=elbv2.Protocol.HTTP  # Make sure this is set correctly
        )

        # Add WebSocket support to the listener
        backend_service.listener.add_action(
            "WebSocketUpgrade",
            priority=1,
            action=elbv2.ListenerAction.forward([backend_service.target_group]),
            conditions=[
                elbv2.ListenerCondition.path_patterns(["/ws"]),
                elbv2.ListenerCondition.http_header("Upgrade", ["websocket"])
            ]
        )     # Add WebSocket support to the listener 
        # Frontend Service
        frontend_service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self,
            "FrontendService",
            cluster=cluster,
            cpu=512,
            memory_limit_mib=1024,
            runtime_platform=runtime_platform,
            task_image_options=ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
                image=ecs.ContainerImage.from_ecr_repository(
                    frontend_repo, tag="latest"
                ),
                container_port=8501,
                container_name="streamlit",
                environment={
                    "PYTHONUNBUFFERED": "1",
                    "BACKEND_URL": f"wss://{backend_domain}/ws",
                    "IMAGE_VERSION": "v2",
                    "BACKEND_WS_RETRY_COUNT": "3",
                    "BACKEND_WS_RETRY_DELAY": "1000",
                },
                log_driver=ecs.LogDrivers.aws_logs(
                    log_group=frontend_log_group,
                    stream_prefix="frontend",
                ),
            ),
            public_load_balancer=True,
            desired_count=1,
            certificate=certificate,
            protocol=elbv2.ApplicationProtocol.HTTPS,
            listener_port=443,
        )

        # Configure frontend auto-scaling
        frontend_scaling = frontend_service.service.auto_scale_task_count(
            min_capacity=1,
            max_capacity=2
        )
        frontend_scaling.scale_on_cpu_utilization(
            "CpuScaling",
            target_utilization_percent=70,
            scale_in_cooldown=Duration.seconds(60),
            scale_out_cooldown=Duration.seconds(60)
        )

        # Import the hosted zone
        hosted_zone = route53.HostedZone.from_lookup(
            self, "HostedZone", domain_name=domain_name
        )

        # Initialize Route 53 client
        client = boto3.client("route53")

        # Function to check if a Route 53 record exists
        def record_exists(record_name):
            response = client.list_resource_record_sets(
                HostedZoneId=hosted_zone.hosted_zone_id,
                StartRecordName=record_name,
                StartRecordType="A",
                MaxItems="1"
            )
            return any(record['Name'].strip('.') == record_name for record in response['ResourceRecordSets'])

        # Conditionally create the Frontend and Backend Route 53 records
        if not record_exists(frontend_domain):
            route53.ARecord(
                self,
                "FrontendAliasRecord",
                zone=hosted_zone,
                target=route53.RecordTarget.from_alias(
                    targets.LoadBalancerTarget(frontend_service.load_balancer)
                ),
                record_name=frontend_domain,
            )

        if not record_exists(backend_domain):
            route53.ARecord(
                self,
                "BackendAliasRecord",
                zone=hosted_zone,
                target=route53.RecordTarget.from_alias(
                    targets.LoadBalancerTarget(backend_service.load_balancer)
                ),
                record_name=backend_domain,
            )

        # Stack Outputs
        CfnOutput(
            self,
            "BackendDomain",
            value=backend_domain,
            description="Backend domain name",
        )

        CfnOutput(
            self,
            "BackendUrl",
            value=f"https://{backend_service.load_balancer.load_balancer_dns_name}",
            description="Backend ALB URL",
        )

        CfnOutput(
            self,
            "FrontendDomain",
            value=frontend_domain,
            description="Frontend domain name",
        )

        CfnOutput(
            self,
            "FrontendUrl",
            value=f"https://{frontend_service.load_balancer.load_balancer_dns_name}",
            description="Frontend ALB URL",
        )

        CfnOutput(
            self,
            "BackendAlbDns",
            value=backend_service.load_balancer.load_balancer_dns_name,
            description="Backend ALB DNS name",
        )

        CfnOutput(
            self,
            "FrontendAlbDns",
            value=frontend_service.load_balancer.load_balancer_dns_name,
            description="Frontend ALB DNS name",
        )

        CfnOutput(self, "VpcId", value=vpc.vpc_id, description="VPC ID")

        CfnOutput(
            self, "VpcCidr", value=vpc.vpc_cidr_block, description="VPC CIDR range"
        )