from typing import Optional
from pynamodb.models import Model
from pynamodb.attributes import UnicodeAttribute, BooleanAttribute, NumberAttribute, JSONAttribute
from pydantic import BaseSettings, AnyUrl


class DynamoDBSettings(BaseSettings):
    aws_region: str
    table_name: str
    host: Optional[AnyUrl] = None

    class Config:
        allow_mutation = False

dynamo_settings = DynamoDBSettings()
region = dynamo_settings.aws_region
table_name = dynamo_settings.table_name
host = dynamo_settings.host


class AuthenticatedUserData(Model):
    class Meta:
        region = region
        table_name = table_name
        host = host

    UUID = UnicodeAttribute(hash_key=True)
    cumulative_token_count = NumberAttribute(range_key=True)
    is_subscribed = BooleanAttribute(default=False)
    sandbox_chat_history = JSONAttribute(default={})
