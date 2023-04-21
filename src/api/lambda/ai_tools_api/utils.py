import datetime as dt
import json
import os
import logging
from cryptography.hazmat.primitives import hashes, hmac
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from fastapi import Response, Request, status
from fastapi.responses import JSONResponse
import openai
import boto3
from uuid import UUID
from enum import Enum
from jose import jwe
from ai_tools_lambda_settings import AIToolsLambdaSettings
from botocore.exceptions import ClientError
from pydantic import BaseModel, constr, BaseSettings, Field
from typing import Optional, Sequence, Union
from dynamodb_models import UserDataTableModel
from pynamodb.pagination import ResultIterator
from pynamodb.models import Model
from dynamodb_models import NextJsAuthTableModel, get_eastern_time_previous_day_midnight

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
lambda_settings = AIToolsLambdaSettings()


AUTHENTICATED_USER_ENV_VAR_NAME = "AUTHENTICATED_USER"
UUID_HEADER_NAME = "UUID"
USER_TOKEN_HEADER_NAME = "JWT"
JWT_PAYLOAD_ID_FIELD_NAME = "sub"
EXAMPLES_ENDPOINT_POSTFIX = "examples"
DELIMITER_SEQUENCE = "%!%!%"

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


class AIToolResponse(AIToolModel):
    response: str


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
    authenticate_user_daily_usage_token_limit: int = 8000
    non_authenticate_user_daily_usage_token_limit: int = 2000
    allowed_token_overflow: int = 1000
    days_before_resetting_token_count: dt.timedelta = dt.timedelta(days=1)


def get_names_of_fields_in_model_mapping(model: BaseModel) -> dict[str, str]:
    """Get the names of the fields in the model mapping.

    Args:
        model: The model to get the names of the fields in the model mapping for.

    Returns:
        A dictionary mapping the field names in the model mapping to the field names in the model.
    """
    return {field.name: field.name for field in model.__fields__.values()}

class BaseAIInstructionModel(AIToolModel):
    """
    **Base for all AI Instructions.**

    - tone: The tone of the AI. This is used to determine the tone of the AI's instructions. Each
        class that inherits from this class should define the default tone for the AI and 
        provide instructions on what the tone should impact in the the response.
    """
    tone: Optional[Tone] = Field(
        default=Tone.FORMAL,
        title="Tone of the Response",
        description="The tone of the writing in the response.",
    )


BASE_USER_PROMPT_PREFIX = "Hi! Here are the instructions for you to follow:\n"

def append_field_prompts_to_prompt(model: BaseAIInstructionModel, base_prompt: str) -> str:
    """
    Append the fields in the model to the base prompt.

    Args:
        model: The model to append the fields to the base prompt for.
        base_prompt: The base prompt to append the fields to.

    Returns:
        The base prompt with the fields appended to it.
    """
    base_prompt += "\n"
    for field_name, field_value in model.dict().items():
        if field_value:
            if isinstance(field_value, list):
                if isinstance(field_value[0], Enum):
                    field_value = [field.value for field in field_value]
                field_value = ", ".join(field_value)
            base_prompt += f"{field_name}: {field_value}\n"
    return base_prompt


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
    secret_ = get_secret(lambda_settings.external_api_secret_name, "us-west-2")
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
    # convert the response to a dictionary
    secret_dict = json.loads(get_secret_value_response['SecretString'])
    return secret_dict


def update_user_token_count(user_uuid: UUID, token_count: int) -> None:
    action_list = []
    try:
        user_data_model: UserDataTableModel = UserDataTableModel.get(str(user_uuid))
    except (Model.DoesNotExist, StopIteration):
        user_data_model = UserDataTableModel(str(user_uuid))
    action_list.append(UserDataTableModel.cumulative_token_count.add(token_count))
    if os.environ.get(AUTHENTICATED_USER_ENV_VAR_NAME, False):
        action_list.append(UserDataTableModel.is_authenticated_user.set(True))
    user_data_model.update(actions=action_list)


def docstring_parameter(*sub):
    def dec(obj):
        obj.__doc__ = obj.__doc__.format(*sub)
        return obj
    return dec


def get_derived_encryption_key(secret: str) -> bytes:
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b'',
        info=b'NextAuth.js Generated Encryption Key',
    )
    derived_key = hkdf.derive(secret.encode())
    return derived_key

def get_user_uuid_from_jwt_token(jwt_token: str) -> UUID:
    """Get the user's UUID from the JWT token."""
    jwt_secret = get_secret(lambda_settings.jwt_secret_name, "us-west-2")
    jwt_key = jwt_secret.get(lambda_settings.jwt_secret_key_name)
    jwt_key = get_derived_encryption_key(jwt_key)
    jwt_payload = jwe.decrypt(jwt_token, jwt_key)
    jwt_payload = jwt_payload.decode("utf-8")
    jwt_payload = json.loads(jwt_payload)
    uuid = jwt_payload.get(JWT_PAYLOAD_ID_FIELD_NAME, None)
    if not uuid:
        raise ValueError("No UUID in JWT payload.")
    return UUID(uuid)


def is_user_authenticated(uuid: UUID, user_jwt_token: str) -> bool:
    """
    Check if the user is authenticated.

    For a user to be authenticated, the UUID in the JWT token must match the UUID in the request
    AND the token in the JWT token must match the token in the database.

    Args:
        uuid: The UUID of the user (from the header in the request).
        user_jwt_token: The JWT token of the user (from the header in the request).
    
    Returns:
        True if the user is authenticated, False otherwise.
    """
    jwt_uuid = get_user_uuid_from_jwt_token(user_jwt_token)
    # if uuid != jwt_uuid:
    #     return False
    table_key = f"USER#{str(jwt_uuid)}"
    nextjs_auth_table_model: NextJsAuthTableModel = None
    try:
        nextjs_auth_table_model: NextJsAuthTableModel = NextJsAuthTableModel.get(table_key, table_key)
    except NextJsAuthTableModel.DoesNotExist: # pylint: disable=broad-except
        return False
    uuid_str = nextjs_auth_table_model.pk.split("#")[1]
    if UUID(uuid_str) != jwt_uuid:
        return False
    return True


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
    action_list = []
    try:
        user_data_model: UserDataTableModel = UserDataTableModel.get(str(user_uuid))
    except UserDataTableModel.DoesNotExist:
        return
    last_reset_date = user_data_model.token_count_last_reset_date.replace(tzinfo=None)
    time_delta = dt.datetime.utcnow() - last_reset_date
    if time_delta > runtime_settings.days_before_resetting_token_count:
        user_data_model.update(
            actions=[
                UserDataTableModel.token_count_last_reset_date.set(get_eastern_time_previous_day_midnight()),
                UserDataTableModel.cumulative_token_count.set(0)
            ]
        )


def get_number_of_tokens_before_limit_reached(user_uuid: UUID, runtime_settings: RuntimeSettings) -> int:
    """Get the number of tokens before the user reaches the limit."""
    token_limit = runtime_settings.non_authenticate_user_daily_usage_token_limit
    try:
        user_data_table_model: UserDataTableModel = UserDataTableModel.get(str(user_uuid))
    except UserDataTableModel.DoesNotExist:
        return token_limit
    if runtime_settings.authenticated:
        token_limit = runtime_settings.authenticate_user_daily_usage_token_limit
    return token_limit - user_data_table_model.cumulative_token_count
