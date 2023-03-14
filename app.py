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
from api_gateway_settings import APIGatewaySettings
from ai_tools_lambda_settings import AIToolsLambdaSettings
from ai_tools_stack import AIToolsStack
from user_data_dynamo_stack import UserDataDynamoStack
from dynamo_db_settings import DynamoDBSettings
from nextjs_dynamodb_stack import NextJsDynamodbStack


app = App()

user_data_dynamodb_settings = DynamoDBSettings(
    table_name="user-data",
    partition_key="uuid"
)
dynamo_db_user_data_stack = UserDataDynamoStack(
    scope=app,
    stack_id="dynamo-stack-user-data",
    dynamodb_settings=user_data_dynamodb_settings
)


user_limits_dynamodb_settings = DynamoDBSettings(
    table_name="user-limits",
    partition_key="uuid",
    sort_key="quota_usage"
)
dynamo_db_user_limits_stack = UserDataDynamoStack(
    scope=app,
    stack_id="dynamo-stack-user-limits",
    dynamodb_settings=user_limits_dynamodb_settings
)


dynamo_db_next_js_auth_stack = NextJsDynamodbStack(
    scope=app,
    stack_id="dynamo-stack-next-js-auth"
)


lambda_settings = AIToolsLambdaSettings(
    openai_api_dir="ai_tools_api",
    openai_lambda_id="ai_tools_lambda",
    external_api_secret_name="openai/apikey",
    api_endpoint_secret_key_name="openai_org_id",
    api_key_secret_key_name="openai_api_key",
)
api_gateway_settings = APIGatewaySettings(
    openai_route_prefix="ai-for-u",
    deployment_stage="dev",
    frontend_cors_url="https://aiforu.com",
    development_cors_url="http://localhost:3000"
)

AIToolsStack(
    scope=app,
    stack_id="aiforu-api-stack",
    lambda_settings=lambda_settings,
    api_gateway_settings=api_gateway_settings,
    user_data_table=dynamo_db_user_data_stack.user_data_table,
    user_limits_table=dynamo_db_user_limits_stack.user_data_table,
    next_js_auth_table=dynamo_db_next_js_auth_stack.nextjs_auth_table
)

app.synth()
