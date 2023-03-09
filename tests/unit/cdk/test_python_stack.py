import sys
import os
import pytest
import aws_cdk.assertions as assertions
import aws_cdk as core
from unittest.mock import MagicMock
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)),"../../../cdk/"))
from ai_tools_stack import AIToolsStack

@pytest.mark.usefixtures("lambda_settings", "api_gateway_settings", "dynamodb_settings")
def test_resources_created(lambda_settings, api_gateway_settings, dynamodb_settings):
    app = core.App()
    stack = AIToolsStack(app,
        "python",
        lambda_settings=lambda_settings,
        api_gateway_settings=api_gateway_settings,
        user_data_table=MagicMock(),
        user_limits_table=MagicMock(),
        next_js_auth_table=MagicMock()
    )
    template = assertions.Template.from_stack(stack)

    template.resource_count_is("AWS::Lambda::Function", 1)

    template.resource_count_is("AWS::ApiGateway::RestApi", 1)
