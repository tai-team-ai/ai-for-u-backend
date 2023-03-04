from os import path
import os
from aws_cdk import (
    StackProps,
    Stack,
    CfnOutput
)
from constructs import Construct
import aws_cdk.aws_lambda as lambda_
import aws_cdk.aws_apigateway as apigateway
import aws_cdk.aws_dynamodb as dynamodb

ApiGatewayEndpointStackOutput = 'ApiEndpoint'
ApiGatewayDomainStackOutput = 'ApiDomain'
ApiGatewayStageStackOutput = 'ApiStage'


class PythonStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)


        ddb = dynamodb.Table(self, 'TodosDB',
            partition_key=dynamodb.Attribute(
                name='id',
                type=dynamodb.AttributeType.STRING
            )
        )

        getTodos = lambda_.Function(self, 'getTodos',
            runtime=lambda_.Runtime.PYTHON_3_8,
            code=lambda_.AssetCode.from_asset(path.join(os.getcwd(), 'api/lambda')),
            handler='get_todos.lambda_handler',
            environment={
                "DDB_TABLE": ddb.table_name
            },
            tracing=lambda_.Tracing.ACTIVE
        )
        ddb.grant_read_data(getTodos)


        getTodo = lambda_.Function(self, 'getTodo', 
            runtime=lambda_.Runtime.PYTHON_3_8,
            code=lambda_.AssetCode.from_asset(path.join(os.getcwd(), 'api/lambda')),
            handler='get_todo.lambda_handler',
            environment={
                "DDB_TABLE": ddb.table_name
            },
            tracing=lambda_.Tracing.ACTIVE
        )
        ddb.grant_read_data(getTodo)


        addTodo = lambda_.Function(self, 'addTodo',
            runtime=lambda_.Runtime.PYTHON_3_8,
            code=lambda_.AssetCode.from_asset(path.join(os.getcwd(), 'python/lambda')),
            handler='add_todo.lambda_handler',
            environment={
                "DDB_TABLE": ddb.table_name
            },
            tracing=lambda_.Tracing.ACTIVE
        )
        ddb.grant_read_write_data(addTodo)

        deleteTodo = lambda_.Function(self, 'deleteTodo', 
            runtime=lambda_.Runtime.PYTHON_3_8,
            code=lambda_.AssetCode.from_asset(path.join(os.getcwd(), 'python/lambda')),
            handler='delete_todo.lambda_handler',
            environment={
                "DDB_TABLE": ddb.table_name
            },
            tracing=lambda_.Tracing.ACTIVE
        )
        ddb.grant_read_write_data(deleteTodo)

        updateTodo = lambda_.Function(self, 'updateTodo',
            runtime=lambda_.Runtime.PYTHON_3_8,
            code=lambda_.AssetCode.from_asset(path.join(os.getcwd(), 'python/lambda')),
            handler='update_todo.lambda_handler',
            environment={
                "DDB_TABLE": ddb.table_name
            },
            tracing=lambda_.Tracing.ACTIVE
        )
        ddb.grant_read_write_data(updateTodo)

        apiGateway = apigateway.RestApi(self, 'ApiGateway',
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_credentials=True,
                allow_origins=apigateway.Cors.ALL_ORIGINS,
                allow_methods=["GET", "PUT", "DELETE", "OPTIONS"],
                allow_headers=["Content-Type", "Authorization", "Content-Length", "X-Requested-With"]
            )
        )

        api = apiGateway.root.add_resource('api')

        todos = api.add_resource('todos',
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_credentials=True,
                allow_origins=apigateway.Cors.ALL_ORIGINS,
                allow_methods=["GET", "PUT", "DELETE", "OPTIONS"],
                allow_headers=["Content-Type", "Authorization", "Content-Length", "X-Requested-With"]
            )
        )
        todos.add_method('GET', apigateway.LambdaIntegration(getTodos))
        todos.add_method('POST', apigateway.LambdaIntegration(addTodo))

        todoId = todos.add_resource('{id}', 
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_credentials=True,
                allow_origins=apigateway.Cors.ALL_ORIGINS,
                allow_methods=["GET", "PUT", "DELETE", "OPTIONS"],
                allow_headers=["Content-Type", "Authorization", "Content-Length", "X-Requested-With"]
            )
        )
        todoId.add_method('GET', apigateway.LambdaIntegration(getTodo))
        todoId.add_method('PUT', apigateway.LambdaIntegration(updateTodo))
        todoId.add_method('DELETE', apigateway.LambdaIntegration(deleteTodo))

        CfnOutput(self, ApiGatewayEndpointStackOutput, 
            value=apiGateway.url
        )

        CfnOutput(self, ApiGatewayDomainStackOutput, 
            value=apiGateway.url.split('/')[2]
        )

        CfnOutput(self, ApiGatewayStageStackOutput,
            value=apiGateway.deployment_stage.stage_name
        )

