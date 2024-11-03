#!/usr/bin/env python3
import os

import aws_cdk as cdk
from dotenv import load_dotenv

from infrastructure.infrastructure_stack import AnimalClassifierStack

# Load environment variables from .env file
load_dotenv()

# Set default values if environment variables are not set
account = os.getenv('CDK_DEFAULT_ACCOUNT')
region = os.getenv('CDK_DEFAULT_REGION', 'us-east-1')  # Defaults to us-east-1 if not set

# Assert that required environment variables are provided
assert account, "CDK_DEFAULT_ACCOUNT environment variable is required"

app = cdk.App()

# Create the stack with explicit region
AnimalClassifierStack(app, "AnimalClassifierStack",
    env=cdk.Environment(
        account=account,
        region=region
    ),
    description="Animal Classifier application with FastAPI backend and Streamlit frontend"
)

app.synth()
