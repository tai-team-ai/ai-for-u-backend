from typing import Optional
from datetime import datetime
from enum import Enum
from pynamodb.models import Model
from pynamodb.attributes import UnicodeAttribute, BooleanAttribute, NumberAttribute, JSONAttribute
from pydantic import BaseSettings, AnyUrl, constr, validator, Field

CDK_DEFAULT_REGION_VAR_NAME = "CDK_DEFAULT_REGION"

class SupportedKeyTypes(Enum):
    STRING = "STRING"
    NUMBER = "NUMBER"


class DynamoDBSettings(BaseSettings):
    aws_region: constr(min_length=1, max_length=63) = Field(..., env=CDK_DEFAULT_REGION_VAR_NAME)
    table_name: constr(min_length=1, max_length=63)
    partition_key: constr(min_length=1, max_length=63)
    partition_key_type: SupportedKeyTypes = SupportedKeyTypes.STRING
    sort_key: Optional[str] = None
    sort_key_type: Optional[SupportedKeyTypes] = SupportedKeyTypes.STRING
    secondary_index_name: Optional[str] = None
    secondary_partition_key: Optional[str] = None
    secondary_sort_key: Optional[str] = None
    host: Optional[AnyUrl] = None

    class Config:
        allow_mutation = False

    @validator("sort_key")
    def _ensure_sort_key_string_greater_than_1(cls, v):
        if v is not None and len(v) < 1:
            raise ValueError("sort_key must be a string greater than 1 character")
        return v


USER_DATA_TABLE_SETTINGS = DynamoDBSettings(
    table_name="user-data",
    partition_key="UUID",
    sort_key="cumulative_token_count",
    sort_key_type=SupportedKeyTypes.NUMBER
)

NEXT_JS_AUTH_TABLE_SETTINGS = DynamoDBSettings(
    table_name="next-auth",
    partition_key="pk",
    sort_key="sk",
    secondary_index_name="GSI1",
    secondary_partition_key="GSI1PK",
    secondary_sort_key="GSI1SK"
)

FEEDBACK_TABLE_SETTINGS = DynamoDBSettings(
    table_name="feedback",
    partition_key="feedback_UUID",
    sort_key="timestamp"
)

class UserDataTableModel(Model):
    class Meta:
        region = USER_DATA_TABLE_SETTINGS.aws_region
        table_name = USER_DATA_TABLE_SETTINGS.table_name
        host = USER_DATA_TABLE_SETTINGS.host

    UUID = UnicodeAttribute(hash_key=True, attr_name=USER_DATA_TABLE_SETTINGS.partition_key)
    cumulative_token_count = NumberAttribute(range_key=True, default_for_new=0, attr_name=USER_DATA_TABLE_SETTINGS.sort_key)
    is_subscribed = BooleanAttribute(null=True)
    sandbox_chat_history = JSONAttribute(null=True)


class FeedbackTableModel(Model):
    class Meta:
        region = FEEDBACK_TABLE_SETTINGS.aws_region
        table_name = FEEDBACK_TABLE_SETTINGS.table_name
        host = FEEDBACK_TABLE_SETTINGS.host

    feedback_UUID = UnicodeAttribute(hash_key=True, attr_name=USER_DATA_TABLE_SETTINGS.partition_key)
    timestamp = NumberAttribute(range_key=True, default=datetime.now().timestamp(), attr_name=USER_DATA_TABLE_SETTINGS.sort_key)
    tool_name = UnicodeAttribute()
    user_UUID = UnicodeAttribute()
    tool_logs = JSONAttribute()
    rating = NumberAttribute(null=True)
    feedback = UnicodeAttribute(null=True)


