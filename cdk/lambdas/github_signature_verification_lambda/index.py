# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

# pylint: disable=C0301,R0801,W0613,W1203,W0718
"""
This module contains lambda function code to convert data to verify Github Webhook Signature.
"""

import json
import os
import hmac
import hashlib
import logging
import http.client
from urllib.parse import urlparse
from botocore.exceptions import ClientError
import boto3

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def get_secret():
    """
    This function code is to get Webhook secrets from secrets manager.
    """
    secret_name = os.getenv('github_webhook_secret')
    region_name = os.getenv('region', 'us-east-1')

    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )

    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )
    except ClientError as e:
        logger.error(f"Unable to fetch secret: {e}")
        raise e

    secret = get_secret_value_response['SecretString']

    return json.loads(secret).get('github_webhook_secret')

def verify_signature(secret, body, signature_header):
    """
    This function is to verify  Webhook signature.
    """
    hash_val = hmac.new(secret.encode('utf-8'), body.encode('utf-8'), hashlib.sha256)
    hash_str = hash_val.hexdigest()
    return hmac.compare_digest(hash_str, signature_header)

def validate_url(url):
    """
    This function is to validate API URL.
    """
    parsed_url = urlparse(url)
    if parsed_url.scheme not in ['http', 'https']:
        raise ValueError(f"Unsupported URL scheme: {parsed_url.scheme}")
    return parsed_url

def lambda_handler(event):
    """
    This Lambda function is to validate Github Webhook and forward the payload to Kinesis endpoint.
    """
    # Log at the start of the function
    logger.info(f"Event: {event}")

    # Fetch the GitHub secret
    try:
        github_secret = get_secret()
        logger.info("Successfully fetched GitHub secret")
    except Exception as e:
        logger.error(f"Failed to fetch GitHub secret: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps('Internal Server Error: Secret not fetched')
        }

    headers = event.get('headers')
    signature_header = headers.get('X-Hub-Signature-256')
    if not signature_header:
        logger.error("Missing signature header")
        return {
            'statusCode': 403,
            'body': json.dumps('Forbidden: Missing signature header')
        }

    signature_value = signature_header.split('=')[1]
    body = json.dumps(event.get('body'))

    valid_signature = verify_signature(secret=github_secret, body=json.loads(body), signature_header=signature_value)
    logger.info(f"SHA256 signature valid: {valid_signature}")

    if not valid_signature:
        logger.error("Invalid signature")
        return {
            'statusCode': 403,
            'body': json.dumps('Forbidden: Invalid signature')
        }

    request_context = event['requestContext']
    forward_url = f"https://{request_context['domainName']}/{request_context['stage']}"
    logger.info(f"FORWARD_URL: {forward_url}")

    # Validate the forward URL
    try:
        parsed_url = validate_url(forward_url)
        logger.info(f"Validated FORWARD_URL: {parsed_url.geturl()}")
    except ValueError as e:
        logger.error(f"Invalid URL: {e}")
        return {
            'statusCode': 400,
            'body': json.dumps('Bad Request: Invalid URL')
        }

    # Signature is valid, forward the request to the new API Gateway endpoint
    try:
        conn = http.client.HTTPSConnection(parsed_url.netloc, timeout=10)
        path = parsed_url.path + "/firehose"
        headers['Content-Type'] = 'application/json'
        conn.request("POST", path, body.encode('utf-8'), headers)
        response = conn.getresponse()
        response_body = response.read().decode('utf-8')

        # Construct Lambda function response
        lambda_response = {
            'statusCode': response.status,
            'headers': dict(response.getheaders()),
            'body': response_body
        }

        return lambda_response

    except Exception as e:
        logger.error(f"Error forwarding request: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps('Internal Server Error: Failed to forward request')
        }
