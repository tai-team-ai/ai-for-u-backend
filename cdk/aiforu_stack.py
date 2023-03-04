"""Module defines the stack for api."""

from os import path
import os
from pathlib import Path
import sys
from typing import Optional
from aws_cdk import (
    Stack,
    CfnOutput,
    Duration
)
from constructs import Construct
import aws_cdk.aws_lambda as lambda_
import aws_cdk.aws_dynamodb as dynamodb
import aws_cdk.aws_apigateway as api_gateway
import aws_cdk.aws_iam as iam
from pydantic import BaseSettings
from botocore.exceptions import ClientError

parent_dir = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.join(parent_dir, "src/api/lambda/lambda_dependencies"))
sys.path.append(os.path.join(parent_dir, "src/api/lambda/ai_tools_api"))

from ai_tools_lambda_settings import AIToolsLambdaSettings
from api_gateway_settings import APIGatewaySettings

class DynamoDBSettings(BaseSettings):
    """Settings for the dynamodb table."""
    table_name: str
    partition_key: str
    sort_key: Optional[str] = None

    class Config:
        validate_assignment = True


class AIforUStack(Stack):

    def __init__(
        self,
        scope: Construct,
        stack_id: str,
        lambda_settings: AIToolsLambdaSettings,
        api_gateway_settings: APIGatewaySettings,
        dynamodb_settings: DynamoDBSettings,
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

        openai_route = self.api.root \
            .add_resource(api_gateway_settings.openai_route_prefix) \
            .add_resource("{proxy+}")

        role = iam.Role(
            self,
            self.namer("lambda-role"),
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            role_name=self.namer("lambda-role")
        )
        openai_lambda = self._create_aiforu_tools_lambda(lambda_settings=lambda_settings, gateway_settings=api_gateway_settings, role=role)
        openai_route.add_method(
            http_method="ANY",
            integration=api_gateway.LambdaIntegration(
                handler=openai_lambda,
                proxy=True,
            )
        )

        user_table = dynamodb.Table(
            self,
            self.namer("user-table"),
            table_name=dynamodb_settings.table_name,
            partition_key=dynamodb.Attribute(name=dynamodb_settings.partition_key, type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name=dynamodb_settings.sort_key, type=dynamodb.AttributeType.STRING)
        )
        user_table.grant_full_access(openai_lambda)

        next_auth_table = self._create_next_auth_table()
        next_auth_table.grant_read_data(openai_lambda)
        
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
    
    def _create_next_auth_table(self) -> dynamodb.Table:
        """Create a dynamodb table with the provided name, partition key, and sort key."""
        next_auth_table = dynamodb.Table(self,
            self.namer("next-auth"),
            table_name="next-auth",
            partition_key=dynamodb.Attribute(
                name="pk",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="sk",
                type=dynamodb.AttributeType.STRING
            ),
            time_to_live_attribute="expires"
        )
        return next_auth_table

    def _create_aiforu_tools_lambda(self, lambda_settings: AIToolsLambdaSettings, gateway_settings: APIGatewaySettings, role: iam.Role) -> lambda_.Function:
        """Create a lambda function with the provided id and environment variables."""
        id_ = lambda_settings.openai_lambda_id
        settings_dict = dict_keys_to_uppercase(lambda_settings.dict())
        settings_dict.update(dict_keys_to_uppercase(gateway_settings.dict()))
        assert type(settings_dict) == dict
        entry_dir = Path(os.path.dirname(os.path.realpath(__file__)), '../src/api/lambda/ai_tools_api')
        
        function = lambda_.Function(self,
            self.namer(id_),
            runtime=lambda_.Runtime.PYTHON_3_9,
            code=lambda_.AssetCode.from_asset(str(entry_dir)),
            handler=f"{lambda_settings.openai_api_dir}/{id_}.lambda_handler",
            environment=settings_dict,
            tracing=lambda_.Tracing.ACTIVE,
            layers=[self.create_dependencies_layer(id_, entry_dir)],
            timeout=Duration.seconds(20),
            role=role
        )
        return function

    def create_dependencies_layer(self, lambda_id: str, entry_dir: Path) -> lambda_.LayerVersion:
        """Create a layer with the dependencies for the lambda."""
        requirements_file = Path(entry_dir, 'requirements-lambda.txt')
        output_dir = f'../.build/{lambda_id}'
        python_output_dir = Path(output_dir, 'python')

        os.system(f"pip install -r {requirements_file} -t {python_output_dir}")

        layer_id = f'{lambda_id}-dependencies'
        layer_code = lambda_.Code.from_asset(output_dir)

        return lambda_.LayerVersion(self, layer_id, code=layer_code)


def dict_keys_to_uppercase(dict_: dict) -> dict:
    """Convert all keys in a dictionary to uppercase."""
    return {k.upper(): v for k, v in dict_.items()}
