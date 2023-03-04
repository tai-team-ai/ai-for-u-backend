"""Module defines settings for the """

from pydantic import BaseSettings
from typing import List, Optional
    
class BaseLambdaSettings(BaseSettings):
    """
    Lambda Environment Settings.
    
    This class is used to define the environment variables for the general api lambda functions.
    
    """
    # lambda_role_arn: str = "None"
    
    class Config:
        case_sensitive = False
        