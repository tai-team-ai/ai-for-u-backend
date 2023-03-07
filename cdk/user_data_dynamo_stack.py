

from aws_cdk import Stack
import aws_cdk.aws_dynamodb as dynamodb
import constructs
from dynamo_db_settings import DynamoDBSettings

class UserDataDynamoStack(Stack):

    def __init__(self,
        scope: constructs,
        stack_id: str,
        dynamodb_settings: DynamoDBSettings,
        **kwargs
    ) -> None:
        super().__init__(scope, stack_id, **kwargs)
        self.namer = lambda x: stack_id + "-" + x
        if dynamodb_settings.sort_key is None:
            sort_key = None
        else:
            sort_key = dynamodb.Attribute(name=dynamodb_settings.sort_key, type=dynamodb.AttributeType.STRING)

        self.user_data_table = dynamodb.Table(
            self,
            self.namer("user-table"),
            table_name=dynamodb_settings.table_name,
            partition_key=dynamodb.Attribute(name=dynamodb_settings.partition_key, type=dynamodb.AttributeType.STRING),
            sort_key=sort_key
        )