import ast
import datetime
import logging
from urllib3 import response
from fastapi import Response, Request
import openai
import boto3
from ai_tools_lambda_settings import AIToolsLambdaSettings
from botocore.exceptions import ClientError
from pydantic import BaseModel
from typing import Optional, Union

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
lambda_settings = AIToolsLambdaSettings()


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
    """Sanitize string."""
    return string.strip()

def authenticate_user(token: str) -> bool:
    """Authenticate user."""
    s3 = boto3.client('s3')
    token = token.rstrip('/') 
    logger.info(f"Checking if token {token} exists in s3 bucket {lambda_settings.log_bucket_name}")
    objects = s3.list_objects(Bucket=lambda_settings.log_bucket_name, Prefix=token, Delimiter='/',MaxKeys=1)
    return 'CommonPrefixes' in objects 

async def log_to_s3(
    request: Request,
    response: Response,
    response_body: Union[BaseModel, dict],
    prompts: Optional[dict[str, str]]=None,
    image_raw_sockets: list[response.HTTPResponse]=None
) -> None:
    """Log request and response."""
    s3 = boto3.resource('s3')
    user_token = request.headers.get(lambda_settings.user_token_header_id, None)
    if not user_token:
        raise UserTokenNotFoundError("User token not found in request headers.")
    if isinstance(response_body, BaseModel):
        response_body = response_body.dict()
    response_body = str(response_body)
    
    path = request.url.path
    path = path.replace("/", "-")
    current_time = datetime.datetime.now().strftime("%Y-%m-%d-%H:%M:%S")
    bucket = s3.Object(lambda_settings.log_bucket_name, f"{user_token}/{current_time}{path}/REQUEST-BODY.log")
    request_body = await request.body()
    bucket.put(Body=request_body)
    bucket = s3.Object(lambda_settings.log_bucket_name, f"{user_token}/{current_time}{path}/RESPONSE-BODY.log")
    bucket.put(Body=response_body)
    bucket = s3.Object(lambda_settings.log_bucket_name, f"{user_token}/{current_time}{path}/RAW.log")
    bucket.put(Body=f"Request Headers: {request.headers}\n\nRequest Body: {await request.json()}"\
                    f"\n\nResponse Headers: {response.headers}\n\nResponse Body: {response_body}")
    if prompts:
        for key, value in prompts.items():
            bucket = s3.Object(lambda_settings.log_bucket_name, f"{user_token}/{current_time}{path}/PROMPT-{key}.log")
            bucket.put(Body=value)
    
    if image_raw_sockets:
        for i, image_raw_socket in enumerate(image_raw_sockets):
            key = f"{user_token}/{current_time}{path}/IMAGE-{i}.png"
            bucket = s3.Bucket(lambda_settings.log_bucket_name)
            bucket.upload_fileobj(image_raw_socket.raw, key)


def add_header(response: Response, origin_url: Optional[str]) -> None:
    response.headers['Cache-Control'] = "no-cache"
    response.headers["Access-Control-Allow-Headers"] = "*"
    if origin_url:
        response.headers["Access-Control-Allow-Origin"] = origin_url

def prepare_response(response: Response, request: Request) -> None:
    """Prepare response."""
    origin_url = request.headers.get("origin", None)
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
