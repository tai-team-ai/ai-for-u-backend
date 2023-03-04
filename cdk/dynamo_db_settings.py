

from typing import Optional
from pydantic import BaseSettings


class DynamoDBSettings(BaseSettings):

    """Settings for the dynamodb table."""

    table_name: str
    partition_key: str
    sort_key: Optional[str] = None

    class Config:
        validate_assignment = True