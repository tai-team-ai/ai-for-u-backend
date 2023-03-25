import sys
from pathlib import Path
from aws_cdk import (
    Stack,
    aws_dynamodb as dynamodb
)
from constructs import Construct

sys.path.append(Path(__file__).parent.parent / "src/api/lambda/ai_tools_api")
from dynamodb_models import DynamoDBSettings, SupportedKeyTypes


class DynamodbStack(Stack):

    def __init__(self,
        scope: Construct,
        stack_id: str,
        dynamodb_settings: DynamoDBSettings,
        **kwargs
    ) -> None:
        super().__init__(scope, stack_id, **kwargs)
        self.namer = lambda x: stack_id + "-" + x
        
        settings_to_cdk_map = {
            SupportedKeyTypes.STRING: dynamodb.AttributeType.STRING,
            SupportedKeyTypes.NUMBER: dynamodb.AttributeType.NUMBER
        }

        partition_key = dynamodb.Attribute(
            name=dynamodb_settings.partition_key,
            type=settings_to_cdk_map[dynamodb_settings.partition_key_type]
        )
        
        sort_key = None
        if dynamodb_settings.sort_key:
            sort_key = dynamodb.Attribute(
                name=dynamodb_settings.sort_key,
                type=settings_to_cdk_map[dynamodb_settings.sort_key_type]
            )

        self.table = dynamodb.Table(self,
            self.namer(stack_id),
            table_name=dynamodb_settings.table_name,
            partition_key=partition_key,
            sort_key=sort_key,
            time_to_live_attribute="expires",
        )

        if dynamodb_settings.secondary_index_name:
            self._add_secondary_index(self.table, dynamodb_settings)


    def _add_secondary_index(self, table: dynamodb.Table, settings: DynamoDBSettings) -> None:
        secondary_partition_key = dynamodb.Attribute(
            name=settings.secondary_partition_key,
            type=dynamodb.AttributeType.STRING
        )
        secondary_sort_key = dynamodb.Attribute(
            name=settings.secondary_sort_key,
            type=dynamodb.AttributeType.STRING
        )

        table.add_global_secondary_index(
            index_name=settings.secondary_index_name,
            partition_key=secondary_partition_key,
            sort_key=secondary_sort_key
        )
