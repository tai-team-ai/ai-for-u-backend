from aws_cdk import (
    Stack,
    aws_dynamodb as dynamodb
)
from constructs import Construct


class NextJsDynamodbStack(Stack):

    def __init__(self,
        scope: Construct,
        stack_id: str,
        **kwargs
    ) -> None:
        super().__init__(scope, stack_id, **kwargs)
        self.namer = lambda x: stack_id + "-" + x

        partition_key = dynamodb.Attribute(
            name="pk",
            type=dynamodb.AttributeType.STRING
        )

        sort_key = dynamodb.Attribute(
            name="sk",
            type=dynamodb.AttributeType.STRING
        )

        self.nextjs_auth_table = dynamodb.Table(self,
            self.namer("next-auth-table"),
            table_name="next-auth",
            partition_key=partition_key,
            sort_key=sort_key,
            time_to_live_attribute="expires"
        )

        secondary_partition_key = dynamodb.Attribute(
            name="GSI1PK",
            type=dynamodb.AttributeType.STRING
        )
        secondary_sort_key = dynamodb.Attribute(
            name="GSI1SK",
            type=dynamodb.AttributeType.STRING
        )

        self.nextjs_auth_table.add_global_secondary_index(
            index_name="GSI1",
            partition_key=secondary_partition_key,
            sort_key=secondary_sort_key
        )
