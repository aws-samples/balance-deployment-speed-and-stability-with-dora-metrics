# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

# pylint: disable=C0301,R0801,W1203,W0718

"""
This module contains test cases for stacks
"""

import unittest
import aws_cdk as cdk
from aws_cdk import assertions
from stacks.change_failure_rate_stack import DoraChangeFailureRateStack
from stacks.deployment_frequency_stack import DoraDeploymentFrequencyStack
from stacks.lead_time_for_change_stack import DoraLeadTimeForChangeStack
from stacks.mean_time_to_restore_stack import DoraMeanTimeToRestoreStack

class TestDoraStacks(unittest.TestCase):
    def setUp(self):
        """ Set up the CDK app and stacks for testing """
        self.app = cdk.App()

    def test_change_failure_rate_stack(self):
        stack = DoraChangeFailureRateStack(self.app, "DoraChangeFailureRateStack")
        template = assertions.Template.from_stack(stack)
        resources = template.find_resources("AWS::Lambda::Function")
        assert len(resources) >= 1
        # Assuming more than one Lambda function might be expected

    def test_deployment_frequency_stack(self):
        stack = DoraDeploymentFrequencyStack(self.app, "DoraDeploymentFrequencyStack")
        template = assertions.Template.from_stack(stack)
        resources = template.find_resources("AWS::Lambda::Function")
        assert len(resources) >= 1

    def test_lead_time_for_change_stack(self):
        stack = DoraLeadTimeForChangeStack(self.app, "DoraLeadTimeForChangeStack")
        template = assertions.Template.from_stack(stack)
        resources = template.find_resources("AWS::Lambda::Function")
        assert len(resources) >= 1

    def test_mean_time_to_restore_stack(self):
        stack = DoraMeanTimeToRestoreStack(self.app, "DoraMeanTimeToRestoreStack")
        template = assertions.Template.from_stack(stack)
        resources = template.find_resources("AWS::Lambda::Function")
        assert len(resources) >= 1

if __name__ == '__main__':
    unittest.main()
