# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

# pylint: disable=C0301,R0801,W1203,W0718,W1309
"""
This module contains lambda function code to create lead time for change.
"""
import json
import logging
import os
import re
import sys
import time

import boto3
from dateutil import parser

# Configure the logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

default_branch = os.getenv("default_main_branch")
app_prod_stage_name = os.getenv("app_prod_stage_name")
app_repo_list = os.getenv("app_repo_names")

output_location = os.getenv("github_output_location")
database = os.getenv("github_database")
table = os.getenv("github_table")

# app_repo_list = [name.strip() for name in app_repo_names.split(',')]

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


def lambda_handler(event, _context=None):
    """
    Function code to create lead time for change metrics.
    """

    try:
        logger.info("Received event: %s", json.dumps(event, indent=2))
        pipeline_name = event["detail"]["pipeline"]
        commit_id = event["detail"]["execution-trigger"]["commit-id"]
        repository_name = event["detail"]["execution-trigger"]["full-repository-name"]
        try:
            pipeline_event_time = event["time"]
            logger.info(f"Event time extracted: {pipeline_event_time}")
        except KeyError as ke:
            logger.warning(f"'time' key missing in event: {event}. Error: {str(ke)}")
            raise
        # Query Athena for the earliest commit time
        earliest_commit_time = query_athena_for_commits(commit_id, repository_name)
        if earliest_commit_time:
            logger.info(
                f"Earliest commit time for commit {commit_id} in repository {repository_name} is {earliest_commit_time}"
            )
        else:
            logger.error("Could not find the earliest commit time or query failed.")

        pipeline_event_time_new, earliest_commit_time_new = calculate_lead_time(
            earliest_commit_time, pipeline_event_time, repository_name
        )
        stage_details = get_stage_details(pipeline_name)

        if repository_name in app_repo_list:
            # Trunk-based model - Check if 'DeployPROD' stage is successful
            deploy_stage_success = any(
                stage["name"] == app_prod_stage_name and stage["status"] == "Succeeded"
                for stage in stage_details
            )

            if deploy_stage_success:
                duration = pipeline_event_time_new - earliest_commit_time_new
                duration_seconds = duration.total_seconds()
                if duration_seconds:
                    logger.info("Deployment_frequency_metric for Trunk_Base")
                    lead_time_for_change_metric(duration_seconds)
            else:
                logger.info(
                    "Repo belongs to the team that used Trunk base but stage in non Prod"
                )

        else:
            # GitFlow model
            duration = pipeline_event_time_new - earliest_commit_time_new
            duration_seconds = duration.total_seconds()
            if duration_seconds:
                logger.info("Deployment_frequency_metric for GitFlow")
                lead_time_for_change_metric(duration_seconds)

    except KeyError as e:
        logger.error(f"KeyError occurred: {e}. Event details: {json.dumps(event, indent=2)}")
    except Exception as e:
        logger.error(f"Unexpected error occurred: {str(e)}. Full event: {json.dumps(event, indent=2)}")
    return {"status": "success"}


def validate_input(input_string, pattern):
    """
    Function code to validate_input
    """
    if not re.match(pattern, input_string):
        raise ValueError(f"Invalid input: {input_string}")


def query_athena_for_commits(commit_id, repository_name):
    """
    Function to run athena query for commits
    """
    athena_client = boto3.client("athena")

    query = """WITH UnnestedCommits AS (
    SELECT
    c.id,
    c.message,
    c.timestamp,
    "after",
    repository.full_name
    FROM {}.{} ,UNNEST(commits) AS t(c)
    WHERE
    "after" = {}
    AND repository.full_name = {}
    )
    SELECT
    MIN(UnnestedCommits.timestamp) AS earliest_commit_time
FROM UnnestedCommits"""

    response = athena_client.start_query_execution(
        QueryString=query.format(database, table, commit_id, repository_name),
        QueryExecutionContext={"Database": database},
        ResultConfiguration={
            "OutputLocation": output_location,
        },
    )

    logger.info(f"Query submitted, execution ID: {response['QueryExecutionId']}")

    # Poll the query status until it finishes
    query_status = athena_client.get_query_execution(
        QueryExecutionId=response["QueryExecutionId"]
    )
    start_time = time.time()
    timeout = 300  # 5 minutes
    while True:
        if query_status["QueryExecution"]["Status"]["State"] == "FAILED":
            logger.error("Query failed")
            sys.exit(1)
        elif time.time() - start_time > timeout:
            logger.error("Query timed out")
            sys.exit(1)
        elif query_status["QueryExecution"]["Status"]["State"] == "SUCCEEDED":
            logger.info("Query completed successfully")
            break
        else:
            time.sleep(10)
            logger.info(f"Query is still running. Waiting for few seconds before retrying.")
            break


    try:
        if query_status["QueryExecution"]["Status"]["State"] == "SUCCEEDED":
            result = athena_client.get_query_results(
                QueryExecutionId=response["QueryExecutionId"]
            )
            logger.info(f"Raw query result: {result}")
            if result["ResultSet"]["Rows"][1:]:
                data_row = result["ResultSet"]["Rows"][1]["Data"]
                if data_row and data_row[0].get("VarCharValue"):
                    earliest_commit_time = data_row[0]["VarCharValue"]
                    logger.info(f"Earliest commit time: {earliest_commit_time}")
                    return earliest_commit_time
        return None
    except Exception as e:
        logger.error(f"Error fetching Athena query results: {e}")
        return None


def calculate_lead_time(earliest_commit_time, pipeline_event_time, repository_name):
    """
    Function to calculate lead time
    """
    try:
        pipeline_event_time_new = parser.parse(pipeline_event_time)
        earliest_commit_time_new = parser.parse(earliest_commit_time)
        logger.info(
            f"Repository name: {repository_name} and App repo list: {app_repo_list}"
        )
        return pipeline_event_time_new, earliest_commit_time_new

    except Exception as e:
        logger.error(f"Error occurred: {e}")
        return None


def get_stage_details(pipeline_name):
    """
    Function to get_stage_details for pipeline
    """
    try:
        response = codepipeline_client.get_pipeline_state(name=pipeline_name)

        # Convert datetime objects to strings for logging
        logger.info(
            "Full pipeline state response: %s",
            json.dumps(response, default=str, indent=2),
        )
        stage_details = []
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

        logger.info(
            "Stage details: %s", json.dumps(stage_details, default=str, indent=2)
        )
        return stage_details
    except Exception as e:
        logger.error("Error fetching stage details: %s", str(e))
        return None


def lead_time_for_change_metric(duration_seconds):
    """
    Function to calculate lead time for change metric and adding custom metric to CW
    """
    if duration_seconds is None:
        logger.error("Invalid duration_seconds. Metric not sent to CloudWatch.")
        return
    try:
        cloudwatch = boto3.client("cloudwatch")
        response = cloudwatch.put_metric_data(
            Namespace="DORA",
            MetricData=[
                {
                    "MetricName": "LeadTimeForChange",
                    "Unit": "Seconds",
                    "Value": duration_seconds,
                },
            ],
        )
        logger.info("LeadTimeForChange metric incremented. Response: %s", response)
    except Exception as e:
        logger.error("Error incrementing LeadTimeForChange metric: %s", str(e))
