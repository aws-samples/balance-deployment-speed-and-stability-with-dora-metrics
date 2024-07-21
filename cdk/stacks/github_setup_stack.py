# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

# pylint: disable=C0301,R0914
"""
This module contains CDK code for API Gateway for Github-Webhook and Amazon Kinesis Firehose with athena and Glue query
"""

import json
import os
import cdk_nag
from constants import config
from aws_cdk import Duration, RemovalPolicy, Stack
from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_glue as glue
from aws_cdk import aws_iam as iam
from aws_cdk import aws_kinesisfirehose as kinesisfirehose
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk import aws_s3 as s3
from constructs import Construct


class DoraOpsGithubLogsStack(Stack):

    """
    Setup and configure Kinesis Firehose with transformation lambda to set logs to S3
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        github_destination_bucket_name = config.GITHUB_LOGS_S3_BUCKET
        github_webhook_secret = config.GITHUB_WEBHOOK_SECRET
        firehose_data_transformation_lambda = "firehose_data_transformation_lambda"
        logging_bucket = s3.Bucket(
            self,
            "GithubLogsAccessLoggingBucket",
            removal_policy=RemovalPolicy.DESTROY,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
        )

        logging_bucket.add_to_resource_policy(
            iam.PolicyStatement(
                actions=["s3:*"],
                resources=[logging_bucket.bucket_arn, f"{logging_bucket.bucket_arn}/*"],
                principals=[iam.AnyPrincipal()],
                conditions={"Bool": {"aws:SecureTransport": "false"}},
                effect=iam.Effect.DENY,
            )
        )
        github_logs_bucket = s3.Bucket(
            self,
            "GithubLogsBucket",
            removal_policy=RemovalPolicy.DESTROY,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            server_access_logs_bucket=logging_bucket,
            server_access_logs_prefix="access-logs/",
            bucket_name=f"{github_destination_bucket_name}-{self.account}",
        )
        github_logs_bucket.add_to_resource_policy(
            iam.PolicyStatement(
                actions=["s3:*"],
                resources=[
                    github_logs_bucket.bucket_arn,
                    f"{github_logs_bucket.bucket_arn}/*",
                ],
                principals=[iam.AnyPrincipal()],
                conditions={"Bool": {"aws:SecureTransport": "false"}},
                effect=iam.Effect.DENY,
            )
        )

        lambda_role = iam.Role(
            self,
            "Lambda_Role",
            role_name="firehose_to_s3_lambda_role",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                )
            ],
        )
        cdk_nag.NagSuppressions.add_resource_suppressions(
            [lambda_role],
            [
                {
                    "id": "AwsSolutions-IAM4",
                    "reason": "The basic execution role is required for Lambda functions",
                }

            ],
            apply_to_children=True,
        )
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3:AbortMultipartUpload",
                    "s3:GetBucketLocation",
                    "s3:GetObject",
                    "s3:ListBucket",
                    "s3:ListBucketMultipartUploads",
                    "s3:PutObject",
                ],
                resources=[
                    f"arn:aws:s3:::{github_destination_bucket_name}-{self.account}",
                    f"arn:aws:s3:::{github_destination_bucket_name}-{self.account}/*",
                    github_logs_bucket.bucket_arn,
                ],
            )
        )
        cdk_nag.NagSuppressions.add_resource_suppressions(
            [lambda_role],
            [
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "Actions needed on all the new objects created in s3 bucket",
                },

            ],
            apply_to_children=True,
        )

        lambda_function = lambda_.Function(
            self,
            "KinesisDataTransformationLambda",
            function_name=firehose_data_transformation_lambda,
            runtime=lambda_.Runtime.PYTHON_3_12,
            role=lambda_role,
            handler="index.lambda_handler",
            memory_size=1024,
            timeout=Duration.minutes(10),
            code=lambda_.Code.from_asset(
                os.path.join(
                    os.path.dirname(__file__),
                    "../lambdas/kinesis_data_transformation_lambda",
                )
            ),
        )
        cdk_nag.NagSuppressions.add_resource_suppressions(
            [lambda_function ],
            [
                cdk_nag.NagPackSuppression(
                    id="AwsSolutions-L1",
                    reason="3_12 is latest",
                )
            ]
        )
        firehose_log_group = logs.LogGroup(
            self,
            "FirehoseAccessLogs",
            log_group_name="/aws/firehose/FirehoseAPIToS3/logs",
            removal_policy=RemovalPolicy.DESTROY,
        )

        firehose_role = iam.Role(
            self,
            "KinesisFirehoseServiceRole",
            role_name="firehose_to_s3_role",
            assumed_by=iam.ServicePrincipal("firehose.amazonaws.com"),
        )
        firehose_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3:AbortMultipartUpload",
                    "s3:GetBucketLocation",
                    "s3:GetObject",
                    "s3:ListBucket",
                    "s3:ListBucketMultipartUploads",
                    "s3:PutObject",
                ],
                resources=[
                    f"arn:aws:s3:::{github_destination_bucket_name}-{self.account}",
                    f"arn:aws:s3:::{github_destination_bucket_name}-{self.account}/*",
                ],
            )
        )
        firehose_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ec2:DescribeVpcs",
                    "ec2:DescribeVpcAttribute",
                    "ec2:DescribeSubnets",
                    "ec2:DescribeSecurityGroups",
                    "ec2:DescribeNetworkInterfaces",
                    "ec2:CreateNetworkInterface",
                    "ec2:CreateNetworkInterfacePermission",
                    "ec2:DeleteNetworkInterface",
                ],
                resources=["*"],
            )
        )
        firehose_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["logs:PutLogEvents"],
                resources=[
                    f"arn:aws:logs:{self.region}:{self.account}:log-group:{firehose_log_group.log_group_name}:*"
                ],
            )
        )
        cdk_nag.NagSuppressions.add_resource_suppressions(
            [firehose_role],
            [
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "Actions typically apply to all the network interfaces created by Firehose",
                },

            ],
            apply_to_children=True,
        )
        firehose_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["lambda:InvokeFunction", "lambda:GetFunctionConfiguration"],
                resources=[
                    f"arn:aws:lambda:{self.region}:{self.account}:function:{firehose_data_transformation_lambda}",
                    f"arn:aws:lambda:{self.region}:{self.account}:function:{firehose_data_transformation_lambda}:*"
                ],
            )
        )

        processing_configuration = kinesisfirehose.CfnDeliveryStream.ProcessingConfigurationProperty(
            enabled=True,
            processors=[
                kinesisfirehose.CfnDeliveryStream.ProcessorProperty(
                    type="Lambda",
                    parameters=[
                        kinesisfirehose.CfnDeliveryStream.ProcessorParameterProperty(
                            parameter_name="LambdaArn",
                            parameter_value=lambda_function.function_arn,
                        )
                    ],
                )
            ],
        )
        s3_destination_configuration_property = kinesisfirehose.CfnDeliveryStream.ExtendedS3DestinationConfigurationProperty(
            bucket_arn=github_logs_bucket.bucket_arn,
            role_arn=firehose_role.role_arn,
            processing_configuration=processing_configuration,
            cloud_watch_logging_options=kinesisfirehose.CfnDeliveryStream.CloudWatchLoggingOptionsProperty(
                enabled=True,
                log_group_name=firehose_log_group.log_group_name,
                log_stream_name="DestinationDelivery"
            )
        )

        firehose_delivery_stream = kinesisfirehose.CfnDeliveryStream(
            self,
            "FirehoseToS3",
            delivery_stream_name="firehose_s3_stream",
            delivery_stream_type="DirectPut",
            extended_s3_destination_configuration=s3_destination_configuration_property,
            delivery_stream_encryption_configuration_input=kinesisfirehose.CfnDeliveryStream.DeliveryStreamEncryptionConfigurationInputProperty(
                key_type="AWS_OWNED_CMK"
            ),
        )
        cdk_nag.NagSuppressions.add_resource_suppressions(
            firehose_role,
            suppressions=[
                cdk_nag.NagPackSuppression(
                    id="AwsSolutions-KDF1",
                    reason="Already enabled above",
                )
            ],
        )

        api_log_group = logs.LogGroup(
            self,
            "ApiGatewayAccessLogs",
            log_group_name="/aws/apigateway/GithubToFirehoseAPI/access-logs",
            removal_policy=RemovalPolicy.DESTROY,
        )
        # API Gateway setup
        api_role = iam.Role(
            self,
            "APIRole",
            role_name="api_to_firehose_role",
            assumed_by=iam.ServicePrincipal("apigateway.amazonaws.com"),
        )
        api_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "firehose:PutRecord",
                    "firehose:PutRecordBatch",
                ],
                resources=[firehose_delivery_stream.attr_arn],
            )
        )
        api_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:DescribeLogGroups",
                    "logs:DescribeLogStreams",
                    "logs:PutLogEvents",
                    "logs:GetLogEvents",
                    "logs:FilterLogEvents"
                ],
                resources=[f"arn:aws:logs:{self.region}:{self.account}:log-group:{api_log_group.log_group_name}:*"],
            )
        )
        cdk_nag.NagSuppressions.add_resource_suppressions(
            [api_role],
            [
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "Resource-level permissions is not possible to access all the logs",
                },

            ],
            apply_to_children=True,
        )

        # Add Lambda function for GitHub webhook signature verification
        github_webhook_lambda_role = iam.Role(
            self,
            "GithubWebhookVerificationLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                )
            ],
        )
        cdk_nag.NagSuppressions.add_resource_suppressions(
            [github_webhook_lambda_role],
            [
                {
                    "id": "AwsSolutions-IAM4",
                    "reason": "The basic execution role is required for Lambda functions",
                }

            ],
            apply_to_children=True,
        )

        github_webhook_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["secretsmanager:GetSecretValue"],
                resources=[f"arn:aws:secretsmanager:{self.region}:{self.account}:secret:{github_webhook_secret}"],
            )
        )

        github_webhook_lambda = lambda_.Function(
            self,
            "GithubWebhookLambda",
            function_name="github_webhook_lambda",
            runtime=lambda_.Runtime.PYTHON_3_12,
            role=github_webhook_lambda_role,
            handler="index.lambda_handler",
            memory_size=128,
            timeout=Duration.minutes(1),
            environment={
                "region": self.region,
                "github_webhook_secret": github_webhook_secret
            },
            code=lambda_.Code.from_asset(
                os.path.join(
                    os.path.dirname(__file__),
                    "../lambdas/github_signature_verification_lambda",
                )
            )
        )
        cdk_nag.NagSuppressions.add_resource_suppressions(
            [github_webhook_lambda],
            [
                cdk_nag.NagPackSuppression(
                    id="AwsSolutions-L1",
                    reason="3_12 is latest",
                )
            ]
        )

        api = apigateway.RestApi(
            self,
            "GithubToFirehoseAPI",
            rest_api_name="GithubToFirehoseAPI",
            endpoint_configuration={"types": [apigateway.EndpointType.REGIONAL]},
            description="Sends data to Firehose.",
            deploy_options=apigateway.StageOptions(
                logging_level=apigateway.MethodLoggingLevel.INFO,
                data_trace_enabled=True,
                access_log_destination=apigateway.LogGroupLogDestination(api_log_group),
                access_log_format=apigateway.AccessLogFormat.json_with_standard_fields(
                    caller=True,
                    http_method=True,
                    ip=True,
                    protocol=True,
                    request_time=True,
                    resource_path=True,
                    response_length=True,
                    status=True,
                    user=True,
                ),
            ),
        )

        # Add request validator
        request_validator = apigateway.RequestValidator(
            self,
            "RequestValidator",
            rest_api=api,
            validate_request_body=True,
            validate_request_parameters=True,
        )

        # API Gateway integration with Kinesis Firehose
        firehose_integration = apigateway.AwsIntegration(
            service="firehose",
            action="PutRecord",
            integration_http_method="POST",
            options=apigateway.IntegrationOptions(
                credentials_role=api_role,
                integration_responses=[
                    {"statusCode": "200", "responseTemplates": {"application/json": ""}}
                ],
                request_templates={
                    "application/json": json.dumps(
                        {
                            "DeliveryStreamName": firehose_delivery_stream.delivery_stream_name,
                            "Record": {"Data": "$util.base64Encode($input.body)"},
                        }
                    )
                },
                passthrough_behavior=apigateway.PassthroughBehavior.NEVER,
            ),
        )

        # Add POST method to the root of the API to send data to Kinesis Firehose
        api.root.add_method(
            "POST",
            apigateway.LambdaIntegration(github_webhook_lambda),
            method_responses=[{"statusCode": "200"}],
            request_validator=request_validator,
            request_parameters={
                "method.request.header.X-GitHub-Event": True
            }
        )

        # Add a new resource and method for Kinesis Firehose integration
        firehose_resource = api.root.add_resource("firehose")
        firehose_resource.add_method(
            "POST",
            firehose_integration,
            method_responses=[{"statusCode": "200"}],
        )

        cdk_nag.NagSuppressions.add_resource_suppressions(
            [api],
            [
                {
                    "id": "AwsSolutions-APIG4",
                    "reason": "API is only connected with Github Webhook and authorized by lambda proxy",
                },
                {
                    "id": "AwsSolutions-COG4",
                    "reason": "Cognito user pool authorizer is not needed.",
                },

            ],
            apply_to_children=True,
        )

        # Create Glue Database
        glue_database = glue.CfnDatabase(
            self,
            "GlueDatabase",
            catalog_id=f"{self.account}",
            database_input=glue.CfnDatabase.DatabaseInputProperty(
                name=config.GITHUB_DATABASE
            ),
        )
        glue.CfnTable(
            self,
            "MyGlueTable",
            catalog_id=f"{self.account}",
            database_name=glue_database.ref,
            table_input=glue.CfnTable.TableInputProperty(
                name=config.GITHUB_TABLE,
                table_type="EXTERNAL_TABLE",
                parameters={"classification": "json", "EXTERNAL": "TRUE"},
                storage_descriptor=glue.CfnTable.StorageDescriptorProperty(
                    columns=[
                        glue.CfnTable.ColumnProperty(name="ref", type="string"),
                        glue.CfnTable.ColumnProperty(name="after", type="string"),
                        glue.CfnTable.ColumnProperty(
                            name="repository", type="struct<full_name:string>"
                        ),
                        glue.CfnTable.ColumnProperty(
                            name="head_commit",
                            type="struct<id:string,message:string,timestamp:string>",
                        ),
                        glue.CfnTable.ColumnProperty(
                            name="commits",
                            type="array<STRUCT<id:string,message:string,timestamp:string>>",
                        ),
                    ],
                    location=f"s3://{github_destination_bucket_name}-{self.account}/",
                    input_format="org.apache.hadoop.mapred.TextInputFormat",
                    output_format="org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat",
                    serde_info=glue.CfnTable.SerdeInfoProperty(
                        serialization_library="org.openx.data.jsonserde.JsonSerDe"
                    ),
                ),
            ),
        )
