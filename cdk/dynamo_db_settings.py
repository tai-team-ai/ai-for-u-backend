

from typing import Dict, Optional
from pydantic import BaseSettings, root_validator


class DynamoDBSettings(BaseSettings):

    """Settings for the dynamodb table."""

    table_name: str
    partition_key: str
    sort_key: Optional[str] = None

    class Config:
        validate_assignment = True

    @root_validator
    def validate(cls, values: Dict[str, Optional[str]]) -> Dict[str, Optional[str]]:
        for key, value in values.items():
            if value is None:
                continue
            if len(value) == 0:
                raise ValueError(f"{key} cannot be an empty string")
        return values