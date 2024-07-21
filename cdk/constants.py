# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0


"""
File for storing constants that are used throughout the code
"""

from models import Config

# Github and code pipeline AWS account ID and region. Where you have all the infrastructure-as-code
TOOLING_ACCOUNT_ID = ""       # Enter Tooling accountID
TOOLING_ACCOUNT_REGION = "us-east-1"      # Enter default Region

# Centralized Ops AWS account ID and region
OPS_ACCOUNT_ID = ""    # Enter Operatinal accountID
OPS_ACCOUNT_REGION = "us-east-1"      # Enter default Region

TOOLING_CROSS_ACCOUNT_LAMBDA_ROLE = "ToolingCrossAccountLambdaRole"
DEFAULT_MAIN_BRANCH = (
    "main"              # Change accounting to your github default branch name. That is used to deploy on Production.If ypu are using GitFlow.
)

GITHUB_LOGS_S3_BUCKET = "githublogss3bucket"  #change with your default "GITHUB LOGS S3 BUCKET" name. So where you want to save your github logs.
GITHUB_WEBHOOK_SECRET = ""  # Secret name of AWS Secret Manager where you saved your github_webhook_secret.
GITHUB_OUTPUT_LOCATION = "s3://github-athena-dora/"  #change with your default "GITHUB LOGS S3 BUCKET" name.
GITHUB_DATABASE = "github_logs_db"  #Athena db name .
GITHUB_TABLE = "github_logs_table" #Athena db table name .

# for teams with Trunk-based development:
APP_PROD_STAGE_NAME = "DeployPROD"       # If some teams are using Trunk base development. Add the repos that are Trunk base and the final stage name that deploy to production.
APP_REPOSITORY_NAMES = ["repo-app-sample-1", "amazon/github-dora", "app1"]


config = Config(
    TOOLING_ACCOUNT_ID=TOOLING_ACCOUNT_ID,
    TOOLING_ACCOUNT_REGION=TOOLING_ACCOUNT_REGION,
    OPS_ACCOUNT_ID=OPS_ACCOUNT_ID,
    OPS_ACCOUNT_REGION=OPS_ACCOUNT_REGION,
    TOOLING_CROSS_ACCOUNT_LAMBDA_ROLE=TOOLING_CROSS_ACCOUNT_LAMBDA_ROLE,
    DEFAULT_MAIN_BRANCH=DEFAULT_MAIN_BRANCH,
    GITHUB_LOGS_S3_BUCKET=GITHUB_LOGS_S3_BUCKET,
    GITHUB_WEBHOOK_SECRET=GITHUB_WEBHOOK_SECRET,
    GITHUB_OUTPUT_LOCATION=GITHUB_OUTPUT_LOCATION,
    GITHUB_DATABASE=GITHUB_DATABASE,
    GITHUB_TABLE=GITHUB_TABLE,
    APP_PROD_STAGE_NAME=APP_PROD_STAGE_NAME,
    APP_REPOSITORY_NAMES=APP_REPOSITORY_NAMES,
)
