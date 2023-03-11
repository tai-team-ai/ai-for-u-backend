import os
import sys
import pytest
parent_dir = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.join(parent_dir,"../../../src/api/lambda/dependencies"))
sys.path.append(os.path.join(parent_dir,"../../../src/api/lambda/ai_tools_api"))
sys.path.append(os.path.join(parent_dir,"../../../cdk"))
from ai_tools_lambda_settings import AIToolsLambdaSettings
from api_gateway_settings import APIGatewaySettings
from dynamo_db_settings import DynamoDBSettings

@pytest.fixture
def lambda_settings() -> AIToolsLambdaSettings:
    lambda_settings_dict = {
        'openai_api_dir': "openai_api",
        'openai_lambda_id': 'test_lambda_id',
        'external_api_secret_name': "test_secret_name",
        'api_endpoint_secret_key_name': "test_endpoint_key_name",
        'api_key_secret_key_name': "test_api_key_name",
    }
    return AIToolsLambdaSettings(**lambda_settings_dict)

@pytest.fixture(scope="session")
def api_gateway_settings() -> APIGatewaySettings:
    api_gateway_settings_dict = {
        'openai_route_prefix': "test_route_prefix",
        'deployment_stage': "test_deployment_stage",
    }
    return APIGatewaySettings(**api_gateway_settings_dict)

@pytest.fixture(scope="session")
def dynamodb_settings() -> DynamoDBSettings:
    dynamodb_settings_dict = {
        'table_name': "test_table_name",
        'partition_key': "test_partition_key",
        'sort_key': "test_sort_key",
    }
    return DynamoDBSettings(**dynamodb_settings_dict)