# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

# pylint: disable=C0301,R0801,W1203,W0718,R0914
"""
This module contains lambda function code to create mean time to restore.
"""

import json
import logging
import os
import re

import boto3
from dateutil.parser import parse

logger = logging.getLogger()
logger.setLevel(logging.INFO)

default_branch = os.environ.get("default_main_branch")
app_prod_stage_name = os.environ.get("app_prod_stage_name")
app_repo_list = os.environ.get("app_repo_names")


target_cross_account_role_arns = {
    os.getenv("tooling_account"): os.getenv("tooling_cross_account_role_arn")
}

ssm_client = boto3.client("ssm")


def create_cross_account_client(service_name, target_role_arn):
    """
    method to create create_cross_account_client to access Tooling account.
    """
    sts = boto3.client("sts")
    assumed_role = sts.assume_role(
        RoleArn=target_role_arn, RoleSessionName="CrossAccountAccess"
    )

    # Create a client using the temporary credentials
    return boto3.client(
        service_name,
        aws_access_key_id=assumed_role["Credentials"]["AccessKeyId"],
        aws_secret_access_key=assumed_role["Credentials"]["SecretAccessKey"],
        aws_session_token=assumed_role["Credentials"]["SessionToken"],
    )

codepipeline_client = create_cross_account_client(
    "codepipeline", target_cross_account_role_arns[os.getenv("tooling_account")]
)

def extract_source_branch_name(commit_message):
    """
    Function to create extract_source_branch_name to access Tooling account.
    """
    known_prefixes = ["fix", "hotfix"]
    known_suffixes = ["hotfix", "fix"]

    # Pattern to match the branch name in the commit message
    pattern = r"from [^/]+/(.+?)(?:\n|$)"
    match = re.search(pattern, commit_message)

    if match:
        branch_name = match.group(1)
        logger.info(f"Extracted branch name: {branch_name}")
        parts = branch_name.split("/")
        # If there are exactly three parts, and the first and last parts match known prefixes/suffixes,
        # assume the middle part is the incident ID.
        if (
            len(parts) == 3
            and parts[0] in known_prefixes
            and parts[-1] in known_suffixes
        ):
            incident_id = parts[1]
        # Otherwise, assume the incident ID is the last part.
        else:
            incident_id = parts[-1]
        logger.info(f"Extracted incident ID: {incident_id}")
        return incident_id
    return None


def get_stage_details(pipeline_name):
    """
    method to get stage details for pipeline
    """
    try:
        response = codepipeline_client.get_pipeline_state(name=pipeline_name)

        # Convert datetime objects to strings for logging
        logger.info(
            "Full pipeline state response: %s",
            json.dumps(response, default=str, indent=2),
        )

        if "stageStates" in response:
            stages = response["stageStates"]
            stage_details = [
                {
                    "name": stage["stageName"],
                    "status": stage["latestExecution"]["status"],
                }
                for stage in stages
            ]
        else:
            logger.error("The 'stageStates' key does not exist in the response.")
            return []

        logger.info(
            "Stage details: %s", json.dumps(stage_details, default=str, indent=2)
        )
        return stage_details
    except codepipeline_client.exceptions.PipelineNotFoundException as e:
        logger.error(f"Pipeline not found: {str(e)}")
        return None
    except Exception as e:
        logger.error("Error fetching stage details: %s", str(e))
        return None


def calculate_downtime(creation_time, final_time_str):
    """Calculate downtime between creation and final time."""
    final_time = parse(final_time_str)
    downtime_seconds = (final_time - creation_time).total_seconds()
    return downtime_seconds


def send_to_cloudwatch(pipeline_name, source_reference, downtime_seconds):
    """Send MTTR-OPSITEM metric to CloudWatch."""
    try:
        logger.info(
            f"Sending data to CloudWatch: Downtime: {downtime_seconds} seconds for pipeline {pipeline_name} and reference {source_reference}."
        )
        cloudwatch = boto3.client("cloudwatch")
        response = cloudwatch.put_metric_data(
            Namespace="DORA/MeanTimeToRestore",
            MetricData=[
                {
                    "MetricName": "Downtime-OPS-Item",
                    "Value": downtime_seconds,
                    "Unit": "Seconds",
                }
            ],
        )
        logger.info(f"CloudWatch response: {response}")
        logger.info("Data successfully sent to CloudWatch.")
    except Exception as e:
        logger.error(f"Error sending data to CloudWatch: {e}")


def lambda_handler(event, _context=None):
    """
    Function code to create mean time to restore metric.
    """
    logger.info(f"Processing event: {event}")

    pipeline_name = event["detail"]["pipeline"]
    state = event["detail"]["state"]
    repository_name = event["detail"]["execution-trigger"]["full-repository-name"]
    branch_name = event["detail"]["execution-trigger"]["branch-name"]
    commit_message = event["detail"]["execution-trigger"]["commit-message"]
    # Get Pipeline Details
    try:
        pipeline_details = codepipeline_client.get_pipeline(name=pipeline_name)
        logger.info(f"Pipeline details fetched: {pipeline_details}")
    except codepipeline_client.exceptions.PipelineNotFoundException as e:
        logger.error(f"Pipeline not found: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps("Pipeline not found")
        }
    creation_time = None
    final_time = None
    if branch_name == default_branch and state == "SUCCEEDED":
        final_time = event["time"]

        source_reference = extract_source_branch_name(commit_message)
        logger.info(f"source_ops_item_id: {source_reference}")
        ops_item_filter = [
            {"Key": "OpsItemId", "Values": [source_reference], "Operator": "Equal"}
        ]

        ops_items = ssm_client.describe_ops_items(OpsItemFilters=ops_item_filter)
        logger.info(f"Found list of ops_items: {ops_items}")

        if "OpsItemSummaries" in ops_items and ops_items["OpsItemSummaries"]:
            ops_item = ops_items["OpsItemSummaries"][0]
            logger.info(f"Found match for ops_item: {ops_item}")
            creation_time = ops_item["CreatedTime"]
            logger.info(f"OpsItem creation time: {creation_time}")
        else:
            logger.info(f"No OpsItem found with ID: {source_reference}")

    else:
        logger.warning("No associated pull request found for the commit.")
    stage_details = get_stage_details(pipeline_name)
    if repository_name in app_repo_list:
        # Trunk-based model - Check if 'DeployPROD' stage is successful
        deploy_stage_success = any(
            stage["name"] == app_prod_stage_name and stage["status"] == "Succeeded"
            for stage in stage_details
        )

        if deploy_stage_success:
            downtime_seconds = calculate_downtime(creation_time, final_time)
            if downtime_seconds:
                logger.info("Mean_Time_to Resolve_metric for Trunk_Base")
                if "creation_time" in locals() and "final_time" in locals():
                    send_to_cloudwatch(
                        pipeline_name, source_reference, downtime_seconds
                    )
        else:
            logger.info(
                "Repo belongs to the team that used Trunk base but stage in non Prod"
            )

    else:
        # GitFlow model
        logger.info("Mean_Time_to Resolve_metric for GitFlow")
        if "creation_time" in locals() and "final_time" in locals():
            downtime_seconds = calculate_downtime(creation_time, final_time)
            send_to_cloudwatch(pipeline_name, source_reference, downtime_seconds)
    return {
        "statusCode": 200,
        "body": json.dumps("Mean time to restore metric updated successfully")
    }
