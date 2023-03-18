import ast
import datetime
import logging
from urllib3 import response
from fastapi import Response, Request
import openai
import boto3
from uuid import UUID
from ai_tools_lambda_settings import AIToolsLambdaSettings
from botocore.exceptions import ClientError
from pydantic import BaseModel
from typing import Optional, Union
from dynamodb_models import UserDataTableModel
from pynamodb.pagination import ResultIterator
from pynamodb.models import Model

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
lambda_settings = AIToolsLambdaSettings()


AUTHENTICATED_USER_ENV_VAR_NAME = "AUTHENTICATED_USER"
UUID_HEADER_NAME = "UUID"
EXAMPLES_ENDPOINT_POSTFIX = "-examples"

class UserTokenNotFoundError(Exception):
    """User token not found in request headers."""
    pass


def to_camel_case(string: str) -> str:
    init, *temp = string.split('_')
    return ''.join([init.lower(), *map(str.title, temp)])

class CamelCaseModel(BaseModel):
    class Config:
        alias_generator = to_camel_case
        allow_population_by_field_name = True

def initialize_openai():
    """Initialize OpenAI."""
    secret_ = ast.literal_eval(get_secret(lambda_settings.external_api_secret_name, "us-west-2"))
    openai.organization = secret_.get(lambda_settings.api_endpoint_secret_key_name)
    openai.api_key = secret_.get(lambda_settings.api_key_secret_key_name)

def sanitize_string(string: str) -> str:
    """Replace '\\n' with '\n' and remove whitespace at the end and beginning of the string."""
    string = string.replace("\\n", "\n")
    return string.strip()


def add_header(response: Response, origin_url: Optional[str]) -> None:
    response.headers['Cache-Control'] = "no-cache"
    response.headers["Access-Control-Allow-Headers"] = "*"
    if origin_url:
        response.headers["Access-Control-Allow-Origin"] = origin_url

def prepare_response(response: Response, request: Request) -> None:
    """Prepare response."""
    origin_url = request.headers.get("Origin", None)
    add_header(response, origin_url)


def get_secret(secret_name: str, region: str) -> dict:
    """
    Get secret from AWS Secrets Manager.
    
    :param secret_name: Name of the secret in AWS Secrets Manager.
    :param region: AWS region where the secret is stored.

    :return: Secret as a dictionary.
    """
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region
    )

    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )
    except ClientError as e:
        # For a list of exceptions thrown, see
        # https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html
        raise e
    # Decrypts secret using the associated KMS key.
    return get_secret_value_response['SecretString']


def update_user_token_count(user_uuid: UUID, token_count: int) -> None:
    try:
        results: ResultIterator[UserDataTableModel] = UserDataTableModel.query(str(user_uuid))
        user_data_table_model = next(results)
        new_token_count = token_count + user_data_table_model.cumulative_token_count
        new_user_model = UserDataTableModel(str(user_uuid), new_token_count, sandbox_chat_history=user_data_table_model.sandbox_chat_history)
        user_data_table_model.delete()
    except (Model.DoesNotExist, StopIteration):
        new_user_model = UserDataTableModel(str(user_uuid), token_count)
    new_user_model.save()


def docstring_parameter(*sub):
    def dec(obj):
        obj.__doc__ = obj.__doc__.format(*sub)
        return obj
    return dec
