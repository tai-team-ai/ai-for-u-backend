import ast
import datetime as dt
import logging
from urllib3 import response
from fastapi import Response, Request, status
from fastapi.responses import JSONResponse
import openai
import boto3
from uuid import UUID
from enum import Enum
from ai_tools_lambda_settings import AIToolsLambdaSettings
from botocore.exceptions import ClientError
from pydantic import BaseModel, constr, BaseSettings, Field
from typing import Optional, Union
from dynamodb_models import UserDataTableModel
from pynamodb.pagination import ResultIterator
from pynamodb.models import Model
from dynamodb_models import NextJsAuthTableModel

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
lambda_settings = AIToolsLambdaSettings()



class TokensExhaustedResponse(BaseModel):
    """Define the model for the client error response."""

    message: str = "Tokens exhausted for the day. Please Sign Up for a free account to continue using AIforU or wait until tomorrow to use the AIforU again."


class TokensExhaustedException(Exception):
    pass


error_responses = {
    status.HTTP_429_TOO_MANY_REQUESTS: {
        "model": TokensExhaustedResponse,
    },
}

TOKEN_EXHAUSTED_JSON_RESPONSE = JSONResponse(
    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
    content={"message": "Tokens exhausted for the day."},
)


AUTHENTICATED_USER_ENV_VAR_NAME = "AUTHENTICATED_USER"
UUID_HEADER_NAME = "UUID"
USER_TOKEN_HEADER_NAME = "Token"
EXAMPLES_ENDPOINT_POSTFIX = "examples"
DELIMITER_SEQUENCE = "%!%!%"

class UserTokenNotFoundError(Exception):
    """User token not found in request headers."""
    pass


def to_camel_case(string: str) -> str:
    init, *temp = string.split('_')
    return ''.join([init.lower(), *map(str.title, temp)])

class AIToolModel(BaseModel):
    class Config:
        alias_generator = to_camel_case
        allow_population_by_field_name = True


class Tone(str, Enum):
    FORMAL = "formal"
    INFORMAL = "informal"
    OPTIMISTIC = "optimistic"
    WORRIED = "worried"
    FRIENDLY = "friendly"
    CURIOUS = "curious"
    ASSERTIVE = "assertive"
    ENCOURAGING = "encouraging"
    SURPRISED = "surprised"
    COOPERATIVE = "cooperative"


class AIToolsEndpointName(str, Enum):
    TEXT_REVISOR = "text-revisor"
    COVER_LETTER_WRITER = "cover-letter-writer"
    CATCHY_TITLE_CREATOR = "catchy-title-creator"
    TEXT_SUMMARIZER = "text-summarizer"
    SANDBOX_CHATGPT = "sandbox-chatgpt"


class RuntimeSettings(BaseSettings):
    """Define the runtime settings for the runtime session."""

    authenticated: bool = Field(..., env=AUTHENTICATED_USER_ENV_VAR_NAME)
    authenticate_user_daily_usage_token_limit: int = 15000
    non_authenticate_user_daily_usage_token_limit: int = 7500
    allowed_token_overflow: int = 1000
    days_before_resetting_token_count: dt.timedelta = dt.timedelta(days=1)


class BaseTemplateRequest(AIToolModel):
    """
    **Base request for all templtates.**
    
    **Attributes:**
    - freeform_command: This command allows the user to specify any command they would like, 
        to be appended to the end of the prompt. This could be dangerous, but for now will allow 
        it will help prevent bottlenecks in the users ability to use the templates
    """
    freeform_command: Optional[constr(min_length=0, max_length=200)] = ""
    tone: Optional[Tone] = Tone.FORMAL


SYSTEM_PROMPT_BASE = ("As an AI {ai_purpose}, your job is to {ai_job_description}. In addition to the above instructions, "
    f"I may also provide you with additional commands specified by this list: {list(BaseTemplateRequest.__fields__.keys())}. "
    "You should adhere to the instructions in this commands while maintaining your overall purpose of being an AI {ai_purpose}."
)


class ExamplesResponse(AIToolModel):
    """
    **Base Response for all examples endpoints.**
    
    **Attributes:**
    - example_names: The names of the examples. This is to be used as parallel list 
        to the examples defined in child classes.
    """
    example_names: list[str]

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
        new_user_model = UserDataTableModel(str(user_uuid), cumulative_token_count=new_token_count, sandbox_chat_history=user_data_table_model.sandbox_chat_history)
        user_data_table_model.delete()
    except (Model.DoesNotExist, StopIteration):
        new_user_model = UserDataTableModel(str(user_uuid), cumulative_token_count=token_count)
    new_user_model.save()


def docstring_parameter(*sub):
    def dec(obj):
        obj.__doc__ = obj.__doc__.format(*sub)
        return obj
    return dec


def is_user_authenticated(uuid: UUID, user_token: str) -> bool:
    """Check if the user is authenticated."""
    try:
        nextjs_auth_table_model: NextJsAuthTableModel = NextJsAuthTableModel.get(str(uuid))
        if nextjs_auth_table_model.access_token == user_token:
            return True
    except UserDataTableModel.DoesNotExist: # pylint: disable=broad-except
        pass
    return False


def does_user_have_enough_tokens_to_make_request(user_uuid: UUID, expected_token_count: int) -> bool:
    """Check if the user has enough tokens to make the request."""
    runtime_settings = RuntimeSettings()
    reset_token_count_if_time_elapsed(user_uuid, runtime_settings)
    tokens_left = get_number_of_tokens_before_limit_reached(user_uuid, runtime_settings)
    tokens_left += runtime_settings.allowed_token_overflow
    if tokens_left < expected_token_count:
        return False, tokens_left
    return True, tokens_left


def reset_token_count_if_time_elapsed(user_uuid: UUID, runtime_settings: RuntimeSettings) -> None:
    """Reset the token count if the time has elapsed."""
    try:
        user_data_table_model: UserDataTableModel = UserDataTableModel.get(str(user_uuid))
        last_reset_date = user_data_table_model.token_count_last_reset_date.replace(tzinfo=None)
        time_delta = dt.datetime.utcnow() - last_reset_date
        if time_delta > runtime_settings.days_before_resetting_token_count:
            user_data_table_model.cumulative_token_count = 0
            user_data_table_model.token_count_last_reset_date = dt.datetime.utcnow()
            user_data_table_model.save()
    except UserDataTableModel.DoesNotExist:
        pass


def get_number_of_tokens_before_limit_reached(user_uuid: UUID, runtime_settings: RuntimeSettings) -> int:
    """Get the number of tokens before the user reaches the limit."""
    token_limit = runtime_settings.non_authenticate_user_daily_usage_token_limit
    try:
        user_data_table_model: UserDataTableModel = UserDataTableModel.get(str(user_uuid))
        if runtime_settings.authenticated:
            token_limit = runtime_settings.authenticate_user_daily_usage_token_limit
    except UserDataTableModel.DoesNotExist:
        return token_limit
    return token_limit - user_data_table_model.cumulative_token_count
