"""Module"""
import pytest

@pytest.mark.usefixtures("lambda_settings")
def test_lambda_settings(lambda_settings):
    """Test OpenAILambdaSettings."""
    assert lambda_settings.external_api_secret_name == 'test_secret_name'
    assert lambda_settings.api_endpoint_secret_key_name == 'test_endpoint_key_name'
    assert lambda_settings.api_key_secret_key_name == 'test_api_key_name'

@pytest.mark.usefixtures("api_gateway_settings")
def test_apigateway_settings(api_gateway_settings):
    """Test APIGatewaySettings."""
    assert api_gateway_settings.openai_route_prefix == "test_route_prefix"
    assert api_gateway_settings.deployment_stage == "test_deployment_stage"
