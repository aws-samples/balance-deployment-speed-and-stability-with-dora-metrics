# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

# pylint: disable=C0301,R0801,W0613,W1203

#!/usr/bin/env python3

"""
This CDK Code to create stacks and lambdas for Dora Metrics
"""
import aws_cdk as cdk
import cdk_nag
from constants import config
from stacks.change_failure_rate_stack import DoraOpsChangeFailureRateStack
from stacks.dashboard_stack import DoraOpsMetricsDashboardStack
from stacks.deployment_frequency_stack import DoraOpsDeploymentFrequencyStack
from stacks.github_setup_stack import DoraOpsGithubLogsStack
from stacks.lead_time_for_change_stack import DoraOpsLeadTimeForChangeStack
from stacks.mean_time_to_restore_stack import DoraOpsMeanTimeToRestoreStack
from stacks.tooling_account_stack import DoraToolingEventBridgeStack

app = cdk.App()

# Set tooling environment
tooling_env = cdk.Environment(
    account=config.TOOLING_ACCOUNT_ID, region=config.TOOLING_ACCOUNT_REGION
)

# Set Ops account environment
ops_env = cdk.Environment(
    account=config.OPS_ACCOUNT_ID, region=config.OPS_ACCOUNT_REGION
)

# Print region and account information for simpler validation
print("\U0001F30E Tooling Region: " + tooling_env.region)
print("\U0001F464 Tooling Account: " + tooling_env.account)
print("\U0001F30E Ops Region: " + ops_env.region)
print("\U0001F464 Ops Account: " + ops_env.account)

# Define Stack for Account Ops
DoraOpsDeploymentFrequencyStack = DoraOpsDeploymentFrequencyStack(
    app,
    "DoraOpsDeploymentFrequencyStack",
    env=ops_env,
)
DoraOpsLeadTimeForChangeStack = DoraOpsLeadTimeForChangeStack(
    app, "DoraLeadTimeForChangeStack", env=ops_env
)
DoraOpsChangeFailureRateStack = DoraOpsChangeFailureRateStack(
    app,
    "DoraOpsChangeFailureRateStack",
    env=ops_env,
)
DoraOpsMeanTimeToRestoreStack = DoraOpsMeanTimeToRestoreStack(
    app,
    "DoraOpsMeanTimeToRestoreStack",
    env=ops_env,
)
# Define Stack for Account Tooling
DoraToolingEventBridgeStack = DoraToolingEventBridgeStack(
    app, "DoraToolingEventBridgeStack", env=tooling_env
)
DoraOpsMetricsDashboardStack = DoraOpsMetricsDashboardStack(
    app, "DoraOpsMetricsDashboardStack", env=ops_env
)
DoraOpsGithubLogsStack = DoraOpsGithubLogsStack(
    app,
    "DoraOpsGithubLogsStack",
    env=ops_env,
)

# Run cdk nag checks on CDK app scope
cdk.Aspects.of(app).add(cdk_nag.AwsSolutionsChecks(verbose=True))

app.synth()
