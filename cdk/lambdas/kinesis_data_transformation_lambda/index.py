# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

# pylint: disable=C0301,R0801,W0613,W1203
"""
This module contains lambda function code to convert data to kinesis_data_transformation.
"""
import logging
import base64
import json

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """
    Function code to convert data to kinesis_data_transformation.
    """
    logger.info(f"Processing event: {event}")

    # Process the incoming records
    output = []
    for record in event["records"]:
        try:
            data = base64.b64decode(record["data"]).decode('utf-8')
            data = json.loads(data)
            output_record = {
                "recordId": record["recordId"],
                "result": "Ok",
                "data": record["data"],
            }
            output.append(output_record)
        except (ValueError, TypeError) as e:
            logger.error(f"Record validation failed: {e}")
            output_record = {
                "recordId": record["recordId"],
                "result": "ProcessingFailed",
                "data": record["data"],
            }
            output.append(output_record)

    logger.info(f"Processing completed. Successful records {len([r for r in output if r['result'] == 'Ok'])}.")
    return {"records": output}
