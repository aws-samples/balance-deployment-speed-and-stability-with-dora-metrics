# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

# pylint: disable=C0301,R0801,W1203,W0718

"""
This module contains lambda function code to create deployment_frequency rate.
"""

import json
import logging
import os

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

default_branch = os.getenv("default_main_branch")
app_prod_stage_name = os.getenv("app_prod_stage_name")
app_repo_list = os.getenv("app_repo_names")

target_cross_account_role_arns = {
    os.getenv("tooling_account"): os.getenv("tooling_cross_account_role_arn")
}


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


def lambda_handler(event):
    """
    Function code to create deployment_frequency rate.
    """
    try:
        logger.info("Received event: %s", json.dumps(event, indent=2))
        pipeline_execution_status = event["detail"]["state"]
        pipeline_name = event["detail"]["pipeline"]
        pipeline_details = codepipeline_client.get_pipeline(name=pipeline_name)
        logger.info(f"Pipeline details fetched: {pipeline_details}")

        branch_name, repository_name = extract_branch_from_pipeline_details(
            pipeline_details
        )
        logger.info(f" branch name: {branch_name}")
        stage_details = get_stage_details(pipeline_name)

        # Trunk-based model for app repositories
        if repository_name in app_repo_list:
            # Check if 'Deploy' stage is successful
            deploy_stage_success = any(
                stage["name"] == app_prod_stage_name and stage["status"] == "Succeeded"
                for stage in stage_details
            )
            if deploy_stage_success:
                logger.info("Deployment_frequency_metric for Trunk_Base")
                deployment_frequency_metric()

        # GitFlow model for other repositories
        else:
            # Check if the branch is 'master' and 'Deploy' stage is successful
            if pipeline_execution_status == "SUCCEEDED" and branch_name == "master":
                logger.info("Deployment_frequency_metric for GitFlow")
                deployment_frequency_metric()
        return {
            "statusCode": 200,
            "body": json.dumps("Deployment frequency metric updated successfully"),
        }
    except Exception as e:
        # Log the exception and return an error response
        logger.error("Error processing event: %s", str(e))
        return {"statusCode": 500, "body": json.dumps("Error processing the event")}


def extract_branch_from_pipeline_details(pipeline_details):
    """
    function to extract_branch_from_pipeline_details
    """
    for stage in pipeline_details["pipeline"]["stages"]:
        if stage["name"] == "Source":
            for action in stage["actions"]:
                if action["actionTypeId"]["category"] == "Source":
                    branch_name = action["configuration"].get("BranchName", None)
                    repository_name = action["configuration"].get(
                        "RepositoryName", None
                    )
                    logger.info(
                        f"Extracted branch name: {branch_name} and Repo name {repository_name}"
                    )
                    return branch_name, repository_name
    logger.warning(
        "Didn't find expected 'Source' stage and configuration in pipeline details."
    )
    return None


def get_stage_details(pipeline_name):
    """
    function to get_stage_details
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
    except Exception as e:
        logger.error("Error fetching stage details: %s", str(e))
        return None


def deployment_frequency_metric():
    """
    method to create custom deployment failure metrics.
    """
    try:
        cloudwatch = boto3.client("cloudwatch")
        # Increment the custom metric for Deployment Frequency
        response = cloudwatch.put_metric_data(
            Namespace="DORA",
            MetricData=[
                {
                    "MetricName": "DeploymentFrequency",
                    "Unit": "Count",
                    "Value": 1,
                },
            ],
        )
        logger.info("Deployment frequency metric incremented. Response: %s", response)
    except Exception as e:
        # Log the exception
        logger.error("Error incrementing metric: %s", str(e))
