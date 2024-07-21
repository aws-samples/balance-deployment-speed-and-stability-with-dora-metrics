# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

# pylint: disable=C0301,R0801
"""
This contains an event bridge rule and lambda function to create change failure rate in an ops account.
"""

import os
from constants import config
import cdk_nag
from aws_cdk import Duration, Stack
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from constructs import Construct


class DoraOpsChangeFailureRateStack(Stack):
    """
    This contains an event bridge rule and lambda function to create change failure rate in an ops account.
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        ops_account_id = config.OPS_ACCOUNT_ID
        ops_region = config.OPS_ACCOUNT_REGION

        # Lambda Function to create custom metrics  #
        lambda_role = iam.Role(
            self,
            "DoraChangeFailureRateLambdaRole",
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
                },

            ],
            apply_to_children=True,
        )
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "cloudwatch:PutMetricData"
                ],
                resources=["*"]
            )
        )
        cdk_nag.NagSuppressions.add_resource_suppressions(
            [lambda_role],
            [
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "PutMetricData action does not support resource-level permissions",
                },

            ],
            apply_to_children=True,
        )
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ssm:ListOpsMetadata",
                    "ssm:ListOpsItemEvents",
                    "ssm:GetOpsItem",
                    "ssm:GetOpsSummary",
                    "ssm:GetOpsMetadata",
                    "ssm:ListOpsItemRelatedItems",
                    "ssm:DescribeOpsItems",
                    "ssm:AssociateOpsItemRelatedItem"
                ],
                resources=[
                    f"arn:aws:ssm:{ops_region}:{ops_account_id}:opsitem/*",
                    f"arn:aws:ssm:{ops_region}:{ops_account_id}:*"
                ],
                conditions={
                    "StringEquals": {
                        "aws:PrincipalAccount": ops_account_id
                    }
                }
            )
        )

        lambda_func = lambda_.Function(
            self,
            "DoraChangeFailureRateLambda",
            runtime=lambda_.Runtime.PYTHON_3_12,
            code=lambda_.Code.from_asset(
                os.path.join(
                    os.path.dirname(__file__),
                    "../lambdas/dora_custom_change_failure_rate_metric",
                )
            ),
            role=lambda_role,
            timeout=Duration.minutes(5),
            memory_size=128,
            handler="index.lambda_handler",
        )
        cdk_nag.NagSuppressions.add_resource_suppressions(
            [lambda_func ],
            [
                cdk_nag.NagPackSuppression(
                    id="AwsSolutions-L1",
                    reason="3_12 is latest",
                )
            ],
            apply_to_children=True,
        )

        ops_event_bus = events.EventBus(
            self,
            "ChangeFailureRateCentralizedEventBus",
            event_bus_name="ChangeFailureRateCentralizedEventBus",
        )

        event_rule = events.Rule(
            self,
            "DoraChangeFailureRateRule",
            # event_bus=ops_event_bus,
            enabled=True,
            event_pattern=events.EventPattern(
                source=["aws.ssm"],
                detail_type=["OpsItem Create"],
                detail={"status": ["Open"]},
            ),
        )
        event_rule.add_target(targets.LambdaFunction(lambda_func))

        events.CfnEventBusPolicy(
            self,
            "ops_event_policy_tooling",
            action="events:PutEvents",
            event_bus_name=ops_event_bus.event_bus_name,
            principal=ops_account_id,
            statement_id="ChangeFailureRateReceiverTooling",
        )
