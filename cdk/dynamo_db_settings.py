

from typing import Dict, Optional
from pydantic import BaseSettings, constr, validator


class DynamoDBSettings(BaseSettings):

    """Settings for the dynamodb table."""



    class Config:
        allow_mutation = False
        

