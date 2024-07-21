# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

# pylint: disable=C0301,R0801,W1203,W0718

"""
This module contains test cases for lambda function code to create Deployment Frequency in an ops account.
"""

import json
import os
import boto3
import pytest
from unittest.mock import patch, MagicMock
from aws_lambda_powertools.utilities.typing import LambdaContext
from constants import config

# Mock environment variables
os.environ["default_main_branch"] = config.DEFAULT_MAIN_BRANCH
os.environ["app_prod_stage_name"] = config.APP_PROD_STAGE_NAME
os.environ["app_repo_names"] = ",".join(config.APP_REPOSITORY_NAMES)
os.environ["tooling_account"] = config.TOOLING_ACCOUNT_ID
os.environ["tooling_cross_account_role_arn"] = f"arn:aws:iam::{config.TOOLING_ACCOUNT_ID}:role/{config.TOOLING_CROSS_ACCOUNT_LAMBDA_ROLE}"

# Patch the create_cross_account_client function before importing the Lambda function
with patch("lambdas.dora_custom_deployment_frequency_metric.index.create_cross_account_client") as mock_create_cross_account_client:
    mock_create_cross_account_client.return_value = MagicMock()
    # Import the Lambda function module
    from lambdas.dora_custom_deployment_frequency_metric.index import (
        lambda_handler,
        extract_branch_from_pipeline_details,
        get_stage_details,
        deployment_frequency_metric,
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

        # Mock the get_pipeline method
        mock_codepipeline.get_pipeline.return_value = {
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

        # Mock the get_pipeline_state method
        mock_codepipeline.get_pipeline_state.return_value = {
            "stageStates": [
                {
                    "stageName": "Deploy",
                    "latestExecution": {"status": "Succeeded"}
                }
            ]
        }
        yield mock_codepipeline

def test_lambda_handler_error(cloudwatch_client, codepipeline_client, monkeypatch):
    """
    Test the lambda_handler function when an error occurs.
    """
    event = {
        "detail": {
            "state": "SUCCEEDED",
            "pipeline": "test"  # Generic pipeline name
        }
    }
    context = LambdaContext()

    # Mock boto3 client creation
    monkeypatch.setattr(boto3, 'client', lambda service, **kwargs: cloudwatch_client if service == "cloudwatch" else codepipeline_client)

    # Simulate an error in get_pipeline
    codepipeline_client.get_pipeline.side_effect = Exception("Test exception")

    response = lambda_handler(event)
    assert response == {
        "statusCode": 500,
        "body": json.dumps("Error processing the event")
    }
    cloudwatch_client.put_metric_data.assert_not_called()

def test_extract_branch_from_pipeline_details():
    """
    Test the extract_branch_from_pipeline_details function.
    """
    pipeline_details = {
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
    branch_name, repository_name = extract_branch_from_pipeline_details(pipeline_details)
    assert branch_name == "main"
    assert repository_name == "repo1"

def test_deployment_frequency_metric(cloudwatch_client, monkeypatch):
    """
    Test the deployment_frequency_metric function.
    """
    # Mock boto3 client creation
    monkeypatch.setattr(boto3, 'client', lambda service, **kwargs: cloudwatch_client)

    deployment_frequency_metric()
    cloudwatch_client.put_metric_data.assert_called_once_with(
        Namespace="DORA",
        MetricData=[
            {
                "MetricName": "DeploymentFrequency",
                "Unit": "Count",
                "Value": 1,
            },
        ]
    )
