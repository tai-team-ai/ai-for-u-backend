"""Module defines settings for the """

import os
import sys
from pydantic import  root_validator
from typing import Optional
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)),"../dependencies"))
from base_lambda_settings import BaseLambdaSettings

    
class AIToolsLambdaSettings(BaseLambdaSettings):
    """
    Lambda Environment Settings.
    
    This class is used to define the environment variables for the OpenAI lambda function.
    The openai_lambda_id is used to define the name of the lambda function and must be the 
    same as the name of the file containing the lambda function.
    
    """
    openai_lambda_id: str
    openai_api_dir: str
    external_api_secret_name: Optional[str]
    api_endpoint_secret_key_name: Optional[str]
    api_key_secret_key_name: Optional[str]

    @root_validator()
    def api_secret_keys_exist_if_secret_name(cls, values):
        if "external_api_secret_name" not in values and "api_endpoint_secret_key_name" not in values:
            return values
        if "external_api_secret_name" in values and "api_endpoint_secret_key_name" in values:
            return values
        raise ValueError('Secret name provided but no api endpoint provided')
    
    class Config:
        case_sensitive = False
        