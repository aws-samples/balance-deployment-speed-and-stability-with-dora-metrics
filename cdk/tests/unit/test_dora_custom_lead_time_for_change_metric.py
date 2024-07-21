# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

# pylint: disable=C0301,R0801,W1203,W0718

"""
This module contains test cases for lambda function code to create lead time for change in an ops account.
"""
import os
import boto3
import pytest
from unittest.mock import patch, MagicMock
from aws_lambda_powertools.utilities.typing import LambdaContext
from dateutil import parser
from constants import config

# Mock environment variables
os.environ["default_main_branch"] = config.DEFAULT_MAIN_BRANCH
os.environ["app_prod_stage_name"] = config.APP_PROD_STAGE_NAME
os.environ["app_repo_names"] = ",".join(config.APP_REPOSITORY_NAMES)
os.environ["tooling_account"] = config.TOOLING_ACCOUNT_ID
os.environ["tooling_cross_account_role_arn"] = f"arn:aws:iam::{config.TOOLING_ACCOUNT_ID}:role/{config.TOOLING_CROSS_ACCOUNT_LAMBDA_ROLE}"
os.environ["github_output_location"] = "s3://example-bucket"
os.environ["github_database"] = "example_database"
os.environ["github_table"] = "example_table"

# Patch the create_cross_account_client function before importing the Lambda function
with patch("lambdas.dora_custom_lead_time_for_change_metric.index.create_cross_account_client") as mock_create_cross_account_client:
    mock_create_cross_account_client.return_value = MagicMock()
    # Import the Lambda function module
    from lambdas.dora_custom_lead_time_for_change_metric.index import (
        lambda_handler,
        get_stage_details,
        calculate_lead_time,
        lead_time_for_change_metric,
        query_athena_for_commits,
        validate_input,
    )

@pytest.fixture
def cloudwatch_client():
    with patch("boto3.client") as mock_boto3_client:
        mock_cloudwatch = MagicMock()
        mock_boto3_client.return_value = mock_cloudwatch

        # Mock the put_metric_data method
        mock_cloudwatch.put_metric_data.return_value = {
            "ResponseMetadata": {"HTTPStatusCode": 200}
        }
        yield mock_cloudwatch

@pytest.fixture
def codepipeline_client():
    with patch("boto3.client") as mock_boto3_client:
        mock_codepipeline = MagicMock()
        mock_boto3_client.return_value = mock_codepipeline

        def mock_get_pipeline_state(name):
            if name == "github-dora-test":
                return {
                    "stageStates": [
                        {
                            "stageName": "Deploy",
                            "latestExecution": {"status": "Succeeded"}
                        }
                    ]
                }
            raise mock_codepipeline.exceptions.PipelineNotFoundException(
                {"Error": {"Code": "PipelineNotFoundException", "Message": "Pipeline not found"}},
                "GetPipelineState"
            )

        mock_codepipeline.get_pipeline_state.side_effect = mock_get_pipeline_state
        yield mock_codepipeline

@pytest.fixture
def athena_client():
    with patch("boto3.client") as mock_boto3_client:
        mock_athena = MagicMock()
        mock_boto3_client.return_value = mock_athena

        def mock_start_query_execution(QueryString, QueryExecutionContext, ResultConfiguration):
            return {
                "QueryExecutionId": "1234-5678-91011"
            }

        def mock_get_query_execution(QueryExecutionId):
            return {
                "QueryExecution": {
                    "Status": {
                        "State": "SUCCEEDED"
                    }
                }
            }

        def mock_get_query_results(QueryExecutionId):
            return {
                "ResultSet": {
                    "Rows": [
                        {"Data": [{"VarCharValue": "2023-01-01T00:00:00Z"}]},
                        {"Data": [{"VarCharValue": "2023-01-01T00:00:00Z"}]}
                    ]
                }
            }

        mock_athena.start_query_execution.side_effect = mock_start_query_execution
        mock_athena.get_query_execution.side_effect = mock_get_query_execution
        mock_athena.get_query_results.side_effect = mock_get_query_results
        yield mock_athena

def test_lambda_handler_correct_time_key():
    event = {
        "detail": {
            "state": "SUCCEEDED",
            "pipeline": "github-dora-test",
            "execution-trigger": {
                "commit-id": "abc123",
                "full-repository-name": "repo1"
            },
            "time": "2023-01-01T01:00:00Z"
        }
    }
    result = lambda_handler(event, LambdaContext())
    assert result == {"status": "success"}

def test_get_stage_details(monkeypatch):
    """
    Test the get_stage_details function.
    """
    mock_codepipeline_client = MagicMock()

    # Mock boto3 client to return the mock codepipeline_client
    monkeypatch.setattr(boto3, 'client', lambda service, **kwargs: mock_codepipeline_client if service == "codepipeline" else None)

    # Ensure the get_pipeline_state method on the mock codepipeline_client returns the expected value
    mock_codepipeline_client.get_pipeline_state.return_value = {
        "stageStates": [
            {
                "stageName": "Deploy",
                "latestExecution": {"status": "Succeeded"}
            }
        ]
    }

    # Update the mock to raise PipelineNotFoundException
    mock_codepipeline_client.get_pipeline_state.side_effect = mock_codepipeline_client.exceptions.PipelineNotFoundException(
        {"Error": {"Code": "PipelineNotFoundException", "Message": "Pipeline not found"}},
        "GetPipelineState"
    )

    # Call the function with a non-existent pipeline
    stage_details = get_stage_details("non-existent-pipeline")

    # Assert the pipeline not found scenario
    assert stage_details is None

def test_calculate_lead_time():
    """
    Test the calculate_lead_time function.
    """
    earliest_commit_time = "2023-01-01T00:00:00Z"
    pipeline_event_time = "2023-01-01T01:00:00Z"
    repository_name = "repo1"

    pipeline_event_time_new, earliest_commit_time_new = calculate_lead_time(earliest_commit_time, pipeline_event_time, repository_name)

    assert pipeline_event_time_new == parser.parse(pipeline_event_time)
    assert earliest_commit_time_new == parser.parse(earliest_commit_time)

def test_lead_time_for_change_metric(cloudwatch_client):
    """
    Test the lead_time_for_change_metric function.
    """
    duration_seconds = 3600

    lead_time_for_change_metric(duration_seconds)

    cloudwatch_client.put_metric_data.assert_called_once_with(
        Namespace="DORA",
        MetricData=[
            {
                "MetricName": "LeadTimeForChange",
                "Unit": "Seconds",
                "Value": duration_seconds,
            },
        ],
    )

def test_query_athena_for_commits(monkeypatch, athena_client):
    """
    Test the query_athena_for_commits function.
    """
    monkeypatch.setattr(boto3, 'client', lambda service, **kwargs: athena_client if service == "athena" else None)

    commit_id = "abc123"
    repository_name = "repo1"

    earliest_commit_time = query_athena_for_commits(commit_id, repository_name)

    assert earliest_commit_time == "2023-01-01T00:00:00Z"

def test_validate_input():
    """
    Test the validate_input function.
    """
    valid_input = "fix/incident-123/hotfix"
    invalid_input = "invalid/branch/name with spaces"

    pattern = r"^[a-zA-Z0-9/_-]+$"

    validate_input(valid_input, pattern)

    with pytest.raises(ValueError):
        validate_input(invalid_input, pattern)
