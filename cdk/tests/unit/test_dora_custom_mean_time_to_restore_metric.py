# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

# pylint: disable=C0301,R0801,W1203,W0718

"""
This module contains test cases for lambda function code to create mean time to restore in an ops account.
"""


import json
import os
import boto3
import pytest
from unittest.mock import patch, MagicMock
from aws_lambda_powertools.utilities.typing import LambdaContext
from dateutil.parser import parse
from constants import config


# Mock environment variables
os.environ["default_main_branch"] = config.DEFAULT_MAIN_BRANCH
os.environ["app_prod_stage_name"] = config.APP_PROD_STAGE_NAME
os.environ["app_repo_names"] = ",".join(config.APP_REPOSITORY_NAMES)
os.environ["tooling_account"] = config.TOOLING_ACCOUNT_ID
os.environ["tooling_cross_account_role_arn"] = f"arn:aws:iam::{config.TOOLING_ACCOUNT_ID}:role/{config.TOOLING_CROSS_ACCOUNT_LAMBDA_ROLE}"

# Patch the create_cross_account_client function before importing the Lambda function
with patch("lambdas.dora_custom_mean_time_to_restore_metric.index.create_cross_account_client") as mock_create_cross_account_client:
    mock_create_cross_account_client.return_value = MagicMock()
    # Import the Lambda function module
    from lambdas.dora_custom_mean_time_to_restore_metric.index import (
        lambda_handler,
        extract_source_branch_name,
        get_stage_details,
        calculate_downtime,
        send_to_cloudwatch,
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
def codepipeline_client(monkeypatch):
    mock_codepipeline = MagicMock()

    def mock_boto_client(service, **kwargs):
        if service == "codepipeline":
            return mock_codepipeline
        return MagicMock()

    monkeypatch.setattr(boto3, 'client', mock_boto_client)

    def mock_get_pipeline(name):
        if name == "github-dora-test":
            return {
                "pipeline": {
                    "stages": [
                        {
                            "name": "Source",
                            "actions": [
                                {
                                    "actionTypeId": {"category": "Source"},
                                    "configuration": {
                                        "BranchName": "main",
                                        "RepositoryName": "repo1"
                                    }
                                }
                            ]
                        }
                    ]
                }
            }
        raise mock_codepipeline.exceptions.PipelineNotFoundException(
            {"Error": {"Code": "PipelineNotFoundException", "Message": "Pipeline not found"}},
            "GetPipeline"
        )

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

    mock_codepipeline.get_pipeline.side_effect = mock_get_pipeline
    mock_codepipeline.get_pipeline_state.side_effect = mock_get_pipeline_state
    yield mock_codepipeline

@pytest.fixture
def ssm_client():
    with patch("boto3.client") as mock_boto3_client:
        mock_ssm = MagicMock()
        mock_boto3_client.return_value = mock_ssm

        def mock_describe_ops_items(OpsItemFilters):
            return {
                "OpsItemSummaries": [
                    {
                        "OpsItemId": "incident-123",
                        "CreatedTime": parse("2023-01-01T00:00:00Z")
                    }
                ]
            }

        mock_ssm.describe_ops_items.side_effect = mock_describe_ops_items
        yield mock_ssm

def test_lambda_handler_error(cloudwatch_client, codepipeline_client, ssm_client, monkeypatch):
    """
    Test the lambda_handler function when an error occurs.
    """
    event = {
        "detail": {
            "state": "SUCCEEDED",
            "pipeline": "github-dora-test",
            "execution-trigger": {
                "full-repository-name": "repo1",
                "branch-name": "main",
                "commit-message": "Merge pull request #123 from fix/incident-123/hotfix"
            },
            "time": "2023-01-01T01:00:00Z"
        }
    }
    context = LambdaContext()

    # Mock boto3 client creation
    monkeypatch.setattr(boto3, 'client', lambda service, **kwargs:
    cloudwatch_client if service == "cloudwatch" else
    codepipeline_client if service == "codepipeline" else
    ssm_client
                        )

    # Simulate an error in get_pipeline
    codepipeline_client.get_pipeline.side_effect = Exception("Test exception")

    response = lambda_handler(event, context)
    assert response == {
        "statusCode": 500,
        "body": json.dumps("Pipeline not found")
    }
    cloudwatch_client.put_metric_data.assert_not_called()

def test_extract_source_branch_name():
    """
    Test the extract_source_branch_name function.
    """
    commit_message = "Merge pull request #123 from fix/incident-123/hotfix"
    incident_id = extract_source_branch_name(commit_message)
    assert incident_id

def test_calculate_downtime():
    """
    Test the calculate_downtime function.
    """
    creation_time = parse("2023-01-01T00:00:00Z")
    final_time_str = "2023-01-01T01:00:00Z"
    downtime = calculate_downtime(creation_time, final_time_str)
    assert downtime == 3600

def test_send_to_cloudwatch(cloudwatch_client):
    """
    Test the send_to_cloudwatch function.
    """
    pipeline_name = "github-dora-test"
    source_reference = "incident-123"
    downtime_seconds = 3600

    send_to_cloudwatch(pipeline_name, source_reference, downtime_seconds)

    cloudwatch_client.put_metric_data.assert_called_once_with(
        Namespace="DORA/MeanTimeToRestore",
        MetricData=[
            {
                "MetricName": "Downtime-OPS-Item",
                "Value": downtime_seconds,
                "Unit": "Seconds",
            }
        ],
    )

@pytest.fixture
def mock_codepipeline_client(monkeypatch):
    mock_client = MagicMock()

    # Mock boto3 client to return the mock_codepipeline_client
    monkeypatch.setattr(boto3, 'client', lambda service, **kwargs: mock_client if service == "codepipeline" else None)

    # Ensure the get_pipeline_state method on the mock client returns the expected value
    mock_client.get_pipeline_state.return_value = {
        "stageStates": [
            {
                "stageName": "Deploy",
                "latestExecution": {"status": "Succeeded"}
            }
        ]
    }

    # Mock the exceptions
    mock_client.exceptions.PipelineNotFoundException = Exception

    return mock_client


def test_get_stage_details(mock_codepipeline_client):
    """
    Test the get_stage_details function.
    """
    pipeline_name = "github-dora-test"

    # Update the mock to raise PipelineNotFoundException
    mock_codepipeline_client.get_pipeline_state.side_effect = mock_codepipeline_client.exceptions.PipelineNotFoundException(
        {"Error": {"Code": "PipelineNotFoundException", "Message": "Pipeline not found"}},
        "GetPipelineState"
    )

    # Call the function with a non-existent pipeline
    stage_details = get_stage_details("non-existent-pipeline")

    # Assert the pipeline not found scenario
    assert stage_details is None


