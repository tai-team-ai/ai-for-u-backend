"""Module defines settings for the """

from pydantic import BaseSettings
from typing import List, Optional
from enum import Enum

    
class BaseLambdaSettings(BaseSettings):
    """
    Lambda Environment Settings.
    
    This class is used to define the environment variables for the general api lambda functions.
    
    """
    # aws_region: Region
    
    class Config:
        case_sensitive = False
        # use_enum_values = True
        