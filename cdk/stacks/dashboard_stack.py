# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

# pylint: disable=C0301,R0801

"""
This module contain Dashboard for DORA Metrics(per day, per week, per Month)
"""

from aws_cdk import Duration, Stack
from aws_cdk import aws_cloudwatch as cloudwatch
from constructs import Construct


class DoraOpsMetricsDashboardStack(Stack):
    """
    This class contain Dashboard for 4-DORA Metrics(per day, per week, per Month)
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Base Metrics
        failed_deployments_metric = cloudwatch.Metric(
            namespace="DORA/ChangeFailureRate",
            metric_name="TotalFailedItems",
            statistic="SampleCount",
        )
        total_deployments_metric = cloudwatch.Metric(
            namespace="DORA/DeploymentFrequency",
            metric_name="TotalDeployments",
            statistic="SampleCount",
        )

        # Creating a CloudWatch dashboard
        dashboard = cloudwatch.Dashboard(
            self, "DORADashboard", dashboard_name="DORA_Metrics"
        )
        periods = [
            {"duration": Duration.days(1), "label": "Per Day"},
            {"duration": Duration.days(7), "label": "Per Week"},
            {"duration": Duration.days(30), "label": "Per Month"},
        ]

        for period in periods:

            change_failure_rate_metric_for_period = cloudwatch.MathExpression(
                expression="(m1/m2)*100",
                using_metrics={
                    "m1": failed_deployments_metric,
                    "m2": total_deployments_metric,
                },
                label="Change Failure Rate (%)",
                period=period["duration"],
            )
            mean_time_to_restore_metric_for_period = cloudwatch.Metric(
                namespace="DORA/MeanTimeToRestore",
                metric_name="Downtime-OPS-Item",
                period=period["duration"],
            )

            deployment_frequency_metric_for_period = cloudwatch.Metric(
                namespace="DORA/DeploymentFrequency",
                metric_name="TotalDeployments",
                period=period["duration"],
            )

            lead_time_for_change_metric_for_period = cloudwatch.Metric(
                namespace="DORA/LeadTimeForChange",
                metric_name="LeadTimeForChange",
                period=period["duration"],
                statistic="Average",
            )
            # CloudWatch Dashboard Title
            title_widget = cloudwatch.TextWidget(
                markdown=f"Dashboard for DORA Metrics {period['label']}",
                height=1,
                width=24,
            )

            dashboard.add_widgets(
                title_widget,
                cloudwatch.SingleValueWidget(
                    metrics=[mean_time_to_restore_metric_for_period],
                    title=f"MTTR {period['label']}",
                ),
                cloudwatch.SingleValueWidget(
                    metrics=[change_failure_rate_metric_for_period],
                    title=f"Change Failure Rate {period['label']}",
                ),
                cloudwatch.SingleValueWidget(
                    metrics=[deployment_frequency_metric_for_period],
                    title=f"Deployment Frequency {period['label']}",
                ),
                cloudwatch.SingleValueWidget(
                    metrics=[lead_time_for_change_metric_for_period],
                    title=f"Lead Time for Change {period['label']}",
                ),
            )
