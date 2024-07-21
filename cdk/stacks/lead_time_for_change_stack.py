# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

# pylint: disable=C0301,R0801
"""
This contains an event bridge rule and lambda function to create lead time for change in an ops account.
"""

import json
import os

from constants import config
import cdk_nag
from aws_cdk import Duration, Stack
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from constructs import Construct


class DoraOpsLeadTimeForChangeStack(Stack):
    """
    This contains an event bridge rule and lambda function to create lead time for change in an ops account.
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        tooling_account_id = config.TOOLING_ACCOUNT_ID
        tooling_cross_account_lambda_role = config.TOOLING_CROSS_ACCOUNT_LAMBDA_ROLE
        app_prod_stage_name = config.APP_PROD_STAGE_NAME
        github_output_location = config.GITHUB_OUTPUT_LOCATION
        github_database = config.GITHUB_DATABASE
        github_table = config.GITHUB_TABLE


        # Lambda Function to create custom metrics  #
        lambda_role = iam.Role(
            self,
            "DoraLeadTimeForChangeLambdaRole",
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
                actions=["cloudwatch:PutMetricData"],
                resources=["*"],
            )
        )
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["sts:AssumeRole"],
                resources=[
                    f"arn:aws:iam::{tooling_account_id}:role/{tooling_cross_account_lambda_role}"
                ],
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

        lambda_func = lambda_.Function(
            self,
            "DoraLeadTimeForChangeLambda",
            runtime=lambda_.Runtime.PYTHON_3_12,
            code=lambda_.Code.from_asset(
                os.path.join(
                    os.path.dirname(__file__),
                    "../lambdas/dora_custom_lead_time_for_change_metric",
                )
            ),
            role=lambda_role,
            timeout=Duration.minutes(10),
            memory_size=128,
            environment={
                "tooling_account": tooling_account_id,
                "tooling_cross_account_role_arn": f"arn:aws:iam::{tooling_account_id}:role/{tooling_cross_account_lambda_role}",
                "default_main_branch": config.DEFAULT_MAIN_BRANCH,
                "app_repo_names": json.dumps(
                    [name.strip() for name in config.APP_REPOSITORY_NAMES]
                ),
                "app_prod_stage_name": app_prod_stage_name,
                "github_output_location": github_output_location,
                "github_database": github_database,
                "github_table": github_table,
            },
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
            "LeadTimeForChangeCentralizedEventBus",
            event_bus_name="LeadTimeForChangeCentralizedEventBus",
        )

        event_rule = events.Rule(
            self,
            "DoraLeadTimeForChangeRule",
            event_bus=ops_event_bus,
            enabled=True,
            event_pattern=events.EventPattern(
                account=[tooling_account_id],
                source=["aws.codepipeline"],
                detail_type=["CodePipeline Pipeline Execution State Change"],
                detail={"state": ["SUCCEEDED"]},
            ),
        )
        event_rule.add_target(targets.LambdaFunction(lambda_func))

        events.CfnEventBusPolicy(
            self,
            "ops_event_policy_tooling",
            action="events:PutEvents",
            event_bus_name=ops_event_bus.event_bus_name,
            principal=tooling_account_id,
            statement_id="LeadTimeForChangeReceiverTooling",
        )
