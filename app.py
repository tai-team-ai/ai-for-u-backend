#!/usr/bin/env python3
import os
from pathlib import Path
import sys

from aws_cdk import App

dir_name = os.path.dirname(os.path.realpath(__file__))
api_dir = Path(dir_name, "src/api/lambda")
sys.path.append(os.path.join(dir_name, "cdk"))
sys.path.append(os.path.join(api_dir, "dependencies"))
sys.path.append(os.path.join(api_dir, "ai_tools_api"))
from aiforu_stack import DynamoDBSettings
from api_gateway_settings import APIGatewaySettings
from ai_tools_lambda_settings import AIToolsLambdaSettings
from aiforu_stack import AIforUStack


stack_name = 'AIWriterBackendStack' if 'LOCAL_TESTING' not in os.environ else 'PythonStack'

app = App()

lambda_settings = AIToolsLambdaSettings(
    openai_api_dir="ai_tools_api",
    openai_lambda_id="ai_tools_lambda",
    external_api_secret_name="openai/apikey",
    api_endpoint_secret_key_name="openai_org_id",
    api_key_secret_key_name="openai_api_key",
)
api_gateway_settings = APIGatewaySettings(
    openai_route_prefix="ai-for-u",
    deployment_stage="dev"
)
dynamodb_settings = DynamoDBSettings(
    table_name="user_data",
    partition_key="user_id",
    sort_key="setting_name"
)

AIforUStack(
    scope=app,
    stack_id=stack_name,
    lambda_settings=lambda_settings,
    api_gateway_settings=api_gateway_settings,
    dynamodb_settings=dynamodb_settings
)

app.synth()
