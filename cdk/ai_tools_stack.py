"""Module defines the stack for api."""

from os import path
import os
from pathlib import Path
import sys
from typing import Optional
from aws_cdk import (
    Stack,
    Duration
)
from constructs import Construct
import aws_cdk.aws_lambda as lambda_
import aws_cdk.aws_dynamodb as dynamodb
import aws_cdk.aws_apigateway as api_gateway
import aws_cdk.aws_iam as iam

parent_dir = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.join(parent_dir, "../src/api/lambda/lambda_dependencies"))
sys.path.append(os.path.join(parent_dir, "../src/api/lambda/ai_tools_api"))

from ai_tools_lambda_settings import AIToolsLambdaSettings # pylint: disable=import-error
from api_gateway_settings import APIGatewaySettings # pylint: disable=import-error


class AIToolsStack(Stack):

    def __init__(
        self,
        scope: Construct,
        stack_id: str,
        lambda_settings: AIToolsLambdaSettings,
        api_gateway_settings: APIGatewaySettings,
        user_data_table: dynamodb.Table,
        user_limits_table: dynamodb.Table,
        next_js_auth_table: dynamodb.Table,
        **kwargs
    ) -> None:
        super().__init__(scope, stack_id, **kwargs)
        self.namer = lambda x: stack_id + "-" + x
        self.api = self._create_rest_api(api_gateway_settings=api_gateway_settings)

        self.deployment = api_gateway.Deployment(self, self.namer("deployment"), api=self.api)

        self.stage = api_gateway.Stage(
            self,
            self.namer("stage"),
            deployment=self.deployment,
            stage_name=api_gateway_settings.deployment_stage,
        )
        self.api.deployment_stage = self.stage

        role = iam.Role(
            self,
            self.namer("lambda-role"),
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            role_name=self.namer("lambda-role")
        )
        openai_lambda = self._create_aiforu_tools_lambda(lambda_settings=lambda_settings, gateway_settings=api_gateway_settings, role=role)

        cors_options = api_gateway.CorsOptions(
            allow_origins=[api_gateway_settings.frontend_cors_url],
            allow_methods=["ALL"],
            allow_headers=["*"],
            allow_credentials=True,
        )

        openai_route = self.api.root \
            .add_resource(api_gateway_settings.openai_route_prefix)
        openai_route.add_proxy(
            default_cors_preflight_options=cors_options,
            default_integration=api_gateway.LambdaIntegration(openai_lambda, proxy=True)
        )


        user_data_table.grant_read_data(openai_lambda)
        user_limits_table.grant_read_write_data(openai_lambda)

        next_js_auth_table.grant_read_data(openai_lambda)

    def _create_rest_api(self, api_gateway_settings: APIGatewaySettings) -> api_gateway.RestApi:
        """Create a rest api with the provided id and deployment stage."""
        origins = [api_gateway_settings.frontend_cors_url]
        if api_gateway_settings.development_cors_urls:
            origins.append(api_gateway_settings.development_cors_urls)
        cors_options = api_gateway.CorsOptions(allow_origins=origins)
        rest_api = api_gateway.RestApi(self, "RestApi",
            rest_api_name=self.namer("rest-api"),
            default_cors_preflight_options=cors_options,
        )
        return rest_api

    def _create_aiforu_tools_lambda(self, lambda_settings: AIToolsLambdaSettings, gateway_settings: APIGatewaySettings, role: iam.Role) -> lambda_.Function:
        """Create a lambda function with the provided id and environment variables."""
        id_ = lambda_settings.openai_lambda_id
        settings_dict = dict_keys_to_uppercase(lambda_settings.dict())
        settings_dict.update(dict_keys_to_uppercase(gateway_settings.dict()))
        assert isinstance(settings_dict, dict)
        entry_dir = Path(os.path.dirname(os.path.realpath(__file__)), "../src/api/lambda")
        path_to_requirements = Path(entry_dir, lambda_settings.openai_api_dir, "requirements-lambda.txt")
        asset_code = lambda_.AssetCode.from_asset(
            str(entry_dir),
        )

        function = lambda_.Function(self,
            self.namer(id_),
            runtime=lambda_.Runtime.PYTHON_3_9,
            code=asset_code,
            handler=f"{lambda_settings.openai_api_dir}/{id_}.lambda_handler",
            environment=settings_dict,
            tracing=lambda_.Tracing.ACTIVE,
            layers=[self.create_dependencies_layer(id_, path_to_requirements)],
            timeout=Duration.seconds(20),
            role=role
        )
        return function

    def create_dependencies_layer(self, lambda_id: str, path_to_requirements: Path) -> lambda_.LayerVersion:
        """Create a layer with the dependencies for the lambda."""
        output_dir = f'.build/{lambda_id}'
        python_output_dir = Path(output_dir, 'python')

        os.system(f"pip install -r {path_to_requirements} -t {python_output_dir}  --upgrade")

        layer_id = f'{lambda_id}-dependencies'
        layer_code = lambda_.Code.from_asset(output_dir)

        return lambda_.LayerVersion(self, layer_id, code=layer_code)


def dict_keys_to_uppercase(dict_: dict) -> dict:
    """Convert all keys in a dictionary to uppercase."""
    return {k.upper(): v for k, v in dict_.items()}
