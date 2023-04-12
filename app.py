import os
from pathlib import Path
import sys

from aws_cdk import App, Environment

dir_name = os.path.dirname(os.path.realpath(__file__))
api_dir = Path(dir_name, "src/api/lambda")
sys.path.append(os.path.join(dir_name, "cdk"))
sys.path.append(os.path.join(api_dir, "dependencies"))
sys.path.append(os.path.join(api_dir, "ai_tools_api"))
from api_gateway_settings import APIGatewaySettings
from ai_tools_lambda_settings import AIToolsLambdaSettings
from ai_tools_stack import AIToolsStack, AIToolsStackSettings
from dynamodb_models import (
    USER_DATA_TABLE_SETTINGS,
    NEXT_JS_AUTH_TABLE_SETTINGS,
    FEEDBACK_TABLE_SETTINGS,
)
from dynamodb_stack import DynamodbStack


app = App()

dynamo_db_user_data_stack = DynamodbStack(
    scope=app,
    stack_id="dynamo-stack-user-data",
    dynamodb_settings=USER_DATA_TABLE_SETTINGS
)


dynamo_db_next_js_auth_stack = DynamodbStack(
    scope=app,
    stack_id="dynamo-stack-next-js-auth",
    dynamodb_settings=NEXT_JS_AUTH_TABLE_SETTINGS
)

dynamo_db_feedback_stack = DynamodbStack(
    scope=app,
    stack_id="dynamo-stack-feedback",
    dynamodb_settings=FEEDBACK_TABLE_SETTINGS,
)

# arn:aws:secretsmanager:us-east-1:645860363137:secret:openai/apikey-fMd6JZ
# arn:aws:secretsmanager:us-west-2:645860363137:secret:openai/apikey-gXnzTj
lambda_settings = AIToolsLambdaSettings(
    openai_api_dir="ai_tools_api",
    openai_lambda_id="ai_tools_lambda",
    external_api_secret_name="openai/apikey",
    api_endpoint_secret_key_name="openai_org_id",
    api_key_secret_key_name="openai_api_key",
    jwt_secret_name="dev/jwt-keys",
    jwt_secret_key_name="key",
)
api_gateway_settings = APIGatewaySettings(
    openai_route_prefix="ai-for-u",
    deployment_stage="dev",
    frontend_cors_url="https://aiforu.com",
    development_cors_url="http://localhost:3000"
)

stack_settings = AIToolsStackSettings()

read_only_tables = [
    dynamo_db_next_js_auth_stack.table,
]
read_write_tables = [
    dynamo_db_user_data_stack.table,
    dynamo_db_feedback_stack.table,
]

AIToolsStack(
    scope=app,
    stack_id="aiforu-api-stack",
    lambda_settings=lambda_settings,
    api_gateway_settings=api_gateway_settings,
    read_only_tables=read_only_tables,
    read_write_tables=read_write_tables,
    stack_settings=stack_settings,
)

app.synth()
