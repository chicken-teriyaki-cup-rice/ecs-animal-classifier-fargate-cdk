#!/usr/bin/env python3
import os

import aws_cdk as cdk
from dotenv import load_dotenv

from infrastructure.infrastructure_stack import AnimalClassifierStack

load_dotenv()

account = os.getenv('CDK_DEFAULT_ACCOUNT')
region = os.getenv('CDK_DEFAULT_REGION', 'us-east-1')
certificate_arn = os.getenv('CERTIFICATE_ARN')

assert account, "CDK_DEFAULT_ACCOUNT environment variable is required"
assert certificate_arn, "CERTIFICATE_ARN environment variable is required"

app = cdk.App()

AnimalClassifierStack(app, "AnimalClassifierStack",
    env=cdk.Environment(
        account=account,
        region=region
    ),
    certificate_arn=certificate_arn,
    description="Animal Classifier application with FastAPI backend and Streamlit frontend"
)

app.synth()
