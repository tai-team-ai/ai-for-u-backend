import aws_cdk as core
import aws_cdk.assertions as assertions
import sys
import os
import pytest
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)),"../../../cdk/"))
from aiforu_stack import AIforUStack

@pytest.mark.usefixtures("lambda_settings", "api_gateway_settings", "dynamodb_settings")
def test_resources_created(lambda_settings, api_gateway_settings, dynamodb_settings):
    app = core.App()
    stack = AIforUStack(app,
        "python",
        lambda_settings=lambda_settings,
        api_gateway_settings=api_gateway_settings,
        dynamodb_settings=dynamodb_settings
    )
    template = assertions.Template.from_stack(stack)

    template.resource_count_is("AWS::Lambda::Function", 1)

    template.resource_count_is("AWS::ApiGateway::RestApi", 1)
