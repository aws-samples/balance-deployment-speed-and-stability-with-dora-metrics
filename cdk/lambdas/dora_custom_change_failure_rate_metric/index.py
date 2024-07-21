# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
# pylint: disable=C0301,R0801,W1203,W0718
"""
This module contains lambda function code to create change
failure rate in an ops account.
"""

import json
import logging

import boto3

# Configure the logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event):
    """
    Function code to create change failure rate.
    """
    try:
        logger.info("Received event: %s", json.dumps(event, indent=2))
        detail_type = event["detail-type"]
        ops_item_status = event["detail"]["status"]

        # Check if the OpsItem is created
        if detail_type == "OpsItem Create" and ops_item_status == "Open":
            failed_deployments_metric()
        return {"statusCode": 200, "body": json.dumps("Metric updated successfully")}
    except Exception as e:
        logger.error("Error processing event: %s", str(e))
        return {"statusCode": 500, "body": json.dumps("Error processing the event")}


def failed_deployments_metric():
    """
    method to create custom change failure rate metrics.
    """
    try:
        cloudwatch = boto3.client("cloudwatch")
        response = cloudwatch.put_metric_data(
            Namespace="DORA/ChangeFailureRate",
            MetricData=[
                {"MetricName": "TotalFailedItems", "Unit": "Count", "Value": 1},
            ],
        )
        logger.info("Metric incremented. Response: %s", response)
    except Exception as e:
        logger.error("Error incrementing metric: %s", str(e))
