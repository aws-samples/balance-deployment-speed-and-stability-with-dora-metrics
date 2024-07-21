# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
# pylint: disable=C0301,R0801,W0613,W1203

from pydantic import BaseModel

class Config(BaseModel):
    TOOLING_ACCOUNT_ID: str
    TOOLING_ACCOUNT_REGION: str
    OPS_ACCOUNT_ID: str
    OPS_ACCOUNT_REGION: str
    DEFAULT_MAIN_BRANCH: str
    GITHUB_LOGS_S3_BUCKET: str
    GITHUB_WEBHOOK_SECRET: str
    GITHUB_OUTPUT_LOCATION: str
    GITHUB_DATABASE: str
    GITHUB_TABLE: str
    APP_PROD_STAGE_NAME: str
    APP_REPOSITORY_NAMES: list[str]
    TOOLING_CROSS_ACCOUNT_LAMBDA_ROLE: str
