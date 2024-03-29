import datetime as dt
import pytz
from typing import Optional
import sys
from pathlib import Path
from datetime import datetime
from enum import Enum
from pynamodb.models import Model
from pynamodb.attributes import UnicodeAttribute, BooleanAttribute, NumberAttribute, JSONAttribute, UTCDateTimeAttribute
from pydantic import BaseSettings, AnyUrl, constr, validator


CDK_DEFAULT_REGION_VAR_NAME = "CDK_DEFAULT_REGION"

class SupportedKeyTypes(Enum):
    STRING = "STRING"
    NUMBER = "NUMBER"


def get_eastern_time_previous_day_midnight() -> dt.datetime:
    """Get the eastern time previous day midnight."""
    # Set the timezone to Eastern Standard Time
    est_tz = pytz.timezone('US/Eastern')
    # Get the current UTC time
    current_utc_time = dt.datetime.utcnow()
    # Convert the UTC time to Eastern Standard Time
    current_est_time = current_utc_time.replace(tzinfo=pytz.utc).astimezone(est_tz)
    # Set the time to 2am
    previous_day_12am_est_time = current_est_time.replace(hour=0, minute=0, second=0, microsecond=0)
    # Convert back to UTC time
    previous_day_12am_utc_time = previous_day_12am_est_time.astimezone(pytz.utc).replace(tzinfo=None)
    return previous_day_12am_utc_time


class DynamoDBSettings(BaseSettings):
    aws_region: constr(min_length=1, max_length=63) = "us-west-2"
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
)

class UserDataTableModel(Model):
    class Meta:
        region = USER_DATA_TABLE_SETTINGS.aws_region
        table_name = USER_DATA_TABLE_SETTINGS.table_name
        host = USER_DATA_TABLE_SETTINGS.host

    UUID = UnicodeAttribute(hash_key=True, attr_name=USER_DATA_TABLE_SETTINGS.partition_key)
    cumulative_token_count = NumberAttribute(default=0)
    token_count_last_reset_date = UTCDateTimeAttribute(default=get_eastern_time_previous_day_midnight())
    is_subscribed = BooleanAttribute(null=True)
    sandbox_chat_history = JSONAttribute(null=True)
    email_address = UnicodeAttribute(null=True)
    authenticated_user = BooleanAttribute(null=True)


class NextJsAuthTableModel(Model):
    class Meta:
        region = NEXT_JS_AUTH_TABLE_SETTINGS.aws_region
        table_name = NEXT_JS_AUTH_TABLE_SETTINGS.table_name
        host = NEXT_JS_AUTH_TABLE_SETTINGS.host

    pk = UnicodeAttribute(hash_key=True, attr_name=NEXT_JS_AUTH_TABLE_SETTINGS.partition_key)
    sk = UnicodeAttribute(range_key=True, attr_name=NEXT_JS_AUTH_TABLE_SETTINGS.sort_key)
    GSI1PK = UnicodeAttribute(null=True, attr_name=NEXT_JS_AUTH_TABLE_SETTINGS.secondary_partition_key)
    GSI1SK = UnicodeAttribute(null=True, attr_name=NEXT_JS_AUTH_TABLE_SETTINGS.secondary_sort_key)
    access_token = UnicodeAttribute(null=True)
    email = UnicodeAttribute(null=True)
    email_verified = UnicodeAttribute(null=True)
    expires_at = NumberAttribute(null=True)
    id = UnicodeAttribute(null=True)
    id_token = UnicodeAttribute(null=True)
    image = UnicodeAttribute(null=True)
    name = UnicodeAttribute(null=True)
    provider = UnicodeAttribute(null=True)
    provider_account_id = UnicodeAttribute(null=True, attr_name="providerAccountId")
    scope = UnicodeAttribute(null=True)
    token_type = UnicodeAttribute(null=True)
    type = UnicodeAttribute(null=True)
    user_id = UnicodeAttribute(null=True, attr_name="userId")


class FeedbackTableModel(Model):
    class Meta:
        region = FEEDBACK_TABLE_SETTINGS.aws_region
        table_name = FEEDBACK_TABLE_SETTINGS.table_name
        host = FEEDBACK_TABLE_SETTINGS.host

    feedback_UUID = UnicodeAttribute(hash_key=True, attr_name=FEEDBACK_TABLE_SETTINGS.partition_key)
    timestamp = NumberAttribute(default=datetime.utcnow())
    ai_tool_name = UnicodeAttribute()
    user_UUID = UnicodeAttribute()
    user_prompt_feedback_context = JSONAttribute()
    ai_response_feedback_context = JSONAttribute()
    rating = NumberAttribute()
    written_feedback = UnicodeAttribute(null=True)
