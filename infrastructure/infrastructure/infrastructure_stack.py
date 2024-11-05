from typing import Any

from aws_cdk import (
    CfnOutput,
    Duration,
    Stack,
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
    aws_iam as iam,
)
from aws_cdk import (
    aws_logs as logs,
)
from constructs import Construct


class AnimalClassifierStack(Stack):
    def __init__(self, scope: Construct, id: str, certificate_arn: str, **kwargs: Any) -> None:
        super().__init__(scope, id, **kwargs)

        certificate = acm.Certificate.from_certificate_arn(self, "Certificate", certificate_arn)

        backend_repository_name = self.node.try_get_context("backend_repository_name")
        frontend_repository_name = self.node.try_get_context("frontend_repository_name")

        if not backend_repository_name or not frontend_repository_name:
            raise ValueError("Both repository names must be provided in CDK context")

        backend_repository = ecr.Repository.from_repository_name(
            self, "BackendRepository", repository_name=backend_repository_name
        )
        frontend_repository = ecr.Repository.from_repository_name(
            self, "FrontendRepository", repository_name=frontend_repository_name
        )

        vpc = ec2.Vpc(
            self, 
            "AnimalClassifierVpc",
            max_azs=2,
            nat_gateways=1,
        )

        cluster = ecs.Cluster(
            self, 
            "AnimalClassifierCluster", 
            vpc=vpc,
            container_insights=True,
        )

        frontend_security_group = ec2.SecurityGroup(
            self, 
            "FrontendSecurityGroup",
            vpc=vpc,
            allow_all_outbound=True,
            description="Security group for Streamlit frontend"
        )

        backend_security_group = ec2.SecurityGroup(
            self, 
            "BackendSecurityGroup",
            vpc=vpc,
            allow_all_outbound=True,
            description="Security group for backend API"
        )

        backend_security_group.add_ingress_rule(
            peer=frontend_security_group,
            connection=ec2.Port.tcp(8000),
            description="Allow frontend to backend"
        )

        frontend_security_group.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(8501),
            description="Allow ALB to Streamlit"
        )

        backend_security_group.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(8000),
            description="Allow ALB to backend"
        )

        execution_role = iam.Role(
            self, 
            "ExecutionRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
        )
        execution_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "service-role/AmazonECSTaskExecutionRolePolicy"
            )
        )
        backend_repository.grant_pull(execution_role)
        frontend_repository.grant_pull(execution_role)

        task_role = iam.Role(
            self, 
            "TaskRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
        )

        log_group = logs.LogGroup(
            self, 
            "AnimalClassifierLogGroup",
            retention=logs.RetentionDays.ONE_WEEK,
        )

        backend_task_definition = ecs.FargateTaskDefinition(
            self, 
            "BackendTaskDef",
            memory_limit_mib=1024,
            cpu=512,
            task_role=task_role,
            execution_role=execution_role,
        )
        
        backend_container = backend_task_definition.add_container(
            "BackendContainer",
            image=ecs.ContainerImage.from_ecr_repository(backend_repository, tag="latest"),
            logging=ecs.LogDriver.aws_logs(
                stream_prefix="Backend",
                log_group=log_group,
            ),
            environment={
                "LOG_LEVEL": "INFO",
                "CORS_ORIGINS": "*",
                "PORT": "8000",
                "HOST": "0.0.0.0",
            },
        )
        
        backend_container.add_port_mappings(
            ecs.PortMapping(
                container_port=8000,
                protocol=ecs.Protocol.TCP
            )
        )

        frontend_task_definition = ecs.FargateTaskDefinition(
            self, 
            "FrontendTaskDef",
            memory_limit_mib=1024,
            cpu=512,
            task_role=task_role,
            execution_role=execution_role,
        )
        
        frontend_container = frontend_task_definition.add_container(
            "FrontendContainer",
            image=ecs.ContainerImage.from_ecr_repository(frontend_repository, tag="latest"),
            logging=ecs.LogDriver.aws_logs(
                stream_prefix="Frontend",
                log_group=log_group,
            ),
            environment={
                "LOG_LEVEL": "DEBUG",
                "MAX_FILE_SIZE_MB": "5",
                "DEFAULT_THRESHOLD": "0.3",
                "WEBSOCKET_TIMEOUT": "30",
                "STREAMLIT_SERVER_PORT": "8501",
                "STREAMLIT_SERVER_ADDRESS": "0.0.0.0",
                "STREAMLIT_SERVER_HEADLESS": "true",
            },
        )
        
        frontend_container.add_port_mappings(
            ecs.PortMapping(
                container_port=8501,
                protocol=ecs.Protocol.TCP
            )
        )

        backend_service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self, 
            "BackendService",
            cluster=cluster,
            task_definition=backend_task_definition,
            public_load_balancer=True,
            assign_public_ip=True,
            security_groups=[backend_security_group],
            desired_count=1,
            protocol=elbv2.ApplicationProtocol.HTTP,
            target_protocol=elbv2.ApplicationProtocol.HTTP,
            listener_port=80,
            task_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            health_check_grace_period=Duration.seconds(120),
        )

        backend_service.target_group.configure_health_check(
            path="/health",
            port="8000",
            healthy_http_codes="200",
            interval=Duration.seconds(60),
            timeout=Duration.seconds(30)
        )

        backend_service.listener.add_action(
            "BackendRoutes",
            action=elbv2.ListenerAction.forward(
                target_groups=[backend_service.target_group]
            ),
            conditions=[
                elbv2.ListenerCondition.path_patterns(["/ws", "/api/*", "/health"])
            ],
            priority=50
        )

        backend_service.listener.add_action(
            "WebSocketRoutes",
            action=elbv2.ListenerAction.forward(
                target_groups=[backend_service.target_group]
            ),
            conditions=[
                elbv2.ListenerCondition.path_patterns(["/ws"])
            ],
            priority=51
        )

        backend_url = f"ws://{backend_service.load_balancer.load_balancer_dns_name}/ws"
        frontend_container.add_environment("LOG_LEVEL", "DEBUG")
        frontend_container.add_environment("MAX_FILE_SIZE_MB", "5")
        frontend_container.add_environment("DEFAULT_THRESHOLD", "0.3")
        frontend_container.add_environment("WEBSOCKET_TIMEOUT", "30")
        frontend_container.add_environment("STREAMLIT_SERVER_PORT", "8501")
        frontend_container.add_environment("STREAMLIT_SERVER_ADDRESS", "0.0.0.0")
        frontend_container.add_environment("STREAMLIT_SERVER_HEADLESS", "true")
        frontend_container.add_environment("WEBSOCKET_ENDPOINT", backend_url)

        frontend_service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self, 
            "FrontendService",
            cluster=cluster,
            task_definition=frontend_task_definition,
            public_load_balancer=True,
            assign_public_ip=True,
            security_groups=[frontend_security_group],
            desired_count=1,
            protocol=elbv2.ApplicationProtocol.HTTP,
            target_protocol=elbv2.ApplicationProtocol.HTTP,
            listener_port=80,
            task_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            health_check_grace_period=Duration.seconds(120),
        )

        frontend_service.target_group.configure_health_check(
            path="/_stcore/health",
            port="8501",
            interval=Duration.seconds(60),
            timeout=Duration.seconds(30),
            healthy_threshold_count=2,
            unhealthy_threshold_count=5,
        )

        CfnOutput(
            self, 
            "BackendServiceURL",
            value=f"http://{backend_service.load_balancer.load_balancer_dns_name}",
            description="Backend service URL",
        )

        CfnOutput(
            self, 
            "FrontendServiceURL",
            value=f"http://{frontend_service.load_balancer.load_balancer_dns_name}",
            description="Frontend service URL",
        )
