# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

# pylint: disable=C0301,R0801
"""
This module contains CDK code for setting up EventBridge in Tooling account.
"""


from constants import config
import cdk_nag
from aws_cdk import Stack
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_iam as iam
from constructs import Construct


class DoraToolingEventBridgeStack(Stack):
    """
    This module contains CDK code for setting up EventBridge in Tooling account.
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        tooling_account = config.TOOLING_ACCOUNT_ID
        tooling_region= config.TOOLING_ACCOUNT_REGION
        ops_account = config.OPS_ACCOUNT_ID
        cross_account_lambda_role_name = config.TOOLING_CROSS_ACCOUNT_LAMBDA_ROLE

        # Create an IAM role that allows the centralized AWS account to send events to the EventBridge bus
        policy = iam.PolicyDocument(
            statements=[
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["events:PutEvents"],
                    resources=[
                        f"arn:aws:events:us-east-1:{ops_account}:event-bus/DeploymentFrequencyCentralizedEventBus",
                        f"arn:aws:events:us-east-1:{ops_account}:event-bus/LeadTimeForChangeCentralizedEventBus",
                        f"arn:aws:events:us-east-1:{ops_account}:event-bus/ChangeFailureRateCentralizedEventBus",
                        f"arn:aws:events:us-east-1:{ops_account}:event-bus/MeanTimeToRestoreCentralizedEventBus",
                    ],
                )
            ]
        )
        cross_account_role = iam.Role(
            self,
            "DoraCrossAccountRole",
            assumed_by=iam.ServicePrincipal("events.amazonaws.com"),
            inline_policies={"AllowPutEvents": policy},
        )

        # Create the IAM role in the target account for cross-account access
        tooling_cross_account_lambda_role = iam.Role(
            self,
            "ToolingCrossAccountLambdaRole",
            assumed_by=iam.ArnPrincipal(f"arn:aws:iam::{ops_account}:root"),
            role_name=cross_account_lambda_role_name,
        )

        # Grant the necessary permissions to the target account role
        tooling_cross_account_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["cloudwatch:PutMetricData"],
                resources=["*"],
            )
        )
        cdk_nag.NagSuppressions.add_resource_suppressions(
            [tooling_cross_account_lambda_role],
            [
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "PutMetricData action does not support resource-level permissions",
                },

            ],
            apply_to_children=True,
        )
        tooling_cross_account_lambda_role.add_to_policy(
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
                    f"arn:aws:ssm:{tooling_region}:{tooling_account}:opsitem/*",
                    f"arn:aws:ssm:{tooling_region}:{tooling_account}:*"
                ]
            )
        )

        tooling_cross_account_lambda_role.add_to_policy(
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
                ],
                resources=["*"],
            )
        )
        tooling_cross_account_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "codepipeline:ListPipelineExecutions",
                    "codepipeline:ListPipelines",
                    "codepipeline:ListWebhooks",
                    "codepipeline:ListActionTypes",
                    "codepipeline:GetPipeline",
                    "codepipeline:GetJobDetails",
                    "codepipeline:GetActionType",
                    "codepipeline:ListTagsForResource",
                    "codepipeline:GetPipelineExecution",
                    "codepipeline:ListActionExecutions",
                    "codepipeline:GetThirdPartyJobDetails",
                    "codepipeline:GetPipelineState",
                    "codepipeline:GetPipelineState",
                    "codepipeline:GetPipeline",
                ],
                resources=[f"arn:aws:codepipeline:{tooling_region}:{tooling_account}:*"],
            )
        )
        cdk_nag.NagSuppressions.add_resource_suppressions(
            [tooling_cross_account_lambda_role],
            [
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "Pipelines are auto created and providing each pipline name is not possible.",
                },

            ],
            apply_to_children=True,
        )
        # Create the Deployment Frequency EventBridge rule that triggers when the CodeCommit pull request is updated
        rule1 = events.Rule(
            self,
            "DoraCodePipelineEventBridgeRule",
            event_pattern=events.EventPattern(
                source=["aws.codepipeline"],
                detail_type=["CodePipeline Pipeline Execution State Change"],
            ),
        )
        rule1.add_target(
            targets.EventBus(
                events.EventBus.from_event_bus_arn(
                    self,
                    "DoraDeploymentFrequencyTarget",
                    f"arn:aws:events:us-east-1:{ops_account}:event-bus/DeploymentFrequencyCentralizedEventBus",
                ),
                role=cross_account_role,
            )
        )
        rule1.add_target(
            targets.EventBus(
                events.EventBus.from_event_bus_arn(
                    self,
                    "DoraLeadTimeForChangeTarget",
                    f"arn:aws:events:us-east-1:{ops_account}:event-bus/LeadTimeForChangeCentralizedEventBus",
                ),
                role=cross_account_role,
            )
        )
        rule1.add_target(
            targets.EventBus(
                events.EventBus.from_event_bus_arn(
                    self,
                    "DoraMeanTimeToRestoreTarget",
                    f"arn:aws:events:us-east-1:{ops_account}:event-bus/MeanTimeToRestoreCentralizedEventBus",
                ),
                role=cross_account_role,
            )
        )
