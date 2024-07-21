# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

# pylint: disable=C0301,R0801,W1203,W0718

"""
This module contains test cases for lambda function code to create change
failure rate in an ops account.
"""


import json
import boto3
import pytest
from unittest.mock import patch, MagicMock
from aws_lambda_powertools.utilities.typing import LambdaContext
from lambdas.dora_custom_change_failure_rate_metric.index import (
    failed_deployments_metric,
    lambda_handler,
)

@pytest.fixture
def cloudwatch_client():
    with patch("boto3.client") as mock_boto3_client:
        # Mock the CloudWatch client
        mock_cloudwatch = MagicMock()
        mock_boto3_client.return_value = mock_cloudwatch

        # Mock the put_metric_data method
        mock_cloudwatch.put_metric_data.return_value = {
            "ResponseMetadata": {"HTTPStatusCode": 200}
        }
        # Mock the list_metrics method
        mock_cloudwatch.list_metrics.return_value = {
            "Metrics": [
                {"MetricName": "TotalFailedItems", "Namespace": "DORA/ChangeFailureRate"}
            ]
        }
        yield mock_cloudwatch

def test_lambda_handler_create_ops_item(cloudwatch_client, monkeypatch):
    """
    Test the lambda_handler function when an OpsItem is created.
    """
    event = {"detail-type": "OpsItem Create", "detail": {"status": "Open"}}
    context = LambdaContext()

    # Ensure the boto3 client is mocked
    monkeypatch.setattr(boto3, 'client', lambda service: cloudwatch_client)

    with patch(
            "lambdas.dora_custom_change_failure_rate_metric.index.failed_deployments_metric"
    ) as mock_failed_deployments_metric:
        response = lambda_handler(event)
        mock_failed_deployments_metric.assert_called_once()
        assert response == {
            "statusCode": 200,
            "body": json.dumps("Metric updated successfully"),
        }

def test_lambda_handler_error(cloudwatch_client, monkeypatch):
    """
    Test the lambda_handler function when an error occurs.
    """
    event = {"detail-type": "OpsItem Create", "detail": {"status": "Open"}}
    context = LambdaContext()

    # Ensure the boto3 client is mocked
    monkeypatch.setattr(boto3, 'client', lambda service: cloudwatch_client)

    with patch(
            "lambdas.dora_custom_change_failure_rate_metric.index.failed_deployments_metric",
            side_effect=Exception("Test exception"),
    ):
        response = lambda_handler(event)
        assert response == {
            "statusCode": 500,
            "body": json.dumps("Error processing the event"),
        }

def test_lambda_handler_no_op(cloudwatch_client, monkeypatch):
    """
    Test the lambda_handler function when no OpsItem is created.
    """
    event = {"detail-type": "OpsItem Update", "detail": {"status": "Closed"}}
    context = LambdaContext()

    # Ensure the boto3 client is mocked
    monkeypatch.setattr(boto3, 'client', lambda service: cloudwatch_client)

    response = lambda_handler(event)
    assert response["statusCode"] == 200
    assert json.loads(response["body"]) == "Metric updated successfully"

def test_failed_deployments_metric(cloudwatch_client, monkeypatch):
    """
    Test the failed_deployments_metric function.
    """
    # Ensure the boto3 client is mocked
    monkeypatch.setattr(boto3, 'client', lambda service: cloudwatch_client)

    failed_deployments_metric()

    metrics = cloudwatch_client.list_metrics(Namespace="DORA/ChangeFailureRate")
    assert len(metrics["Metrics"]) == 1
    assert metrics["Metrics"][0]["MetricName"] == "TotalFailedItems"
    assert metrics["Metrics"][0]["Namespace"] == "DORA/ChangeFailureRate"
