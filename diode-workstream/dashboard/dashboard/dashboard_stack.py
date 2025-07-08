from aws_cdk import (
    Duration,
    Stack,
    aws_cloudwatch as cloudwatch,
)
from constructs import Construct
import json

class DashboardStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        mapping_ids = self.node.try_get_context("mapping_ids")
        print(mapping_ids)


        dashboards = {}
        # Define the metrics you want to track
        for mapping in mapping_ids:
        # Create a CloudWatch Dashboard
            dashboards[mapping] = cloudwatch.Dashboard(self, f"{mapping}-MetricsDashboard", 
                dashboard_name=f"DiodeMonitoring-{mapping}",
                # Inherit period from each graph
                period_override=cloudwatch.PeriodOverride.INHERIT)
        ## Bi-Weekly metrics 
            transfer_created_count = cloudwatch.Metric(
                    namespace="AWS/Diode",
                    dimensions_map={"MappingId": mapping},  # Specify the Mapping
                    metric_name="TransferCreatedCount",
                    statistic="Sum",
                    #period=Duration.days(14)
                )
            succeeded_transfer_count = cloudwatch.Metric(
                    namespace="AWS/Diode",
                    dimensions_map={"MappingId": mapping},  # Specify the Mapping
                    metric_name="SucceededTransferCount",
                    statistic="Sum",
                    #period=Duration.days(14)
                )

            
            succeeded_transfer_size = cloudwatch.Metric(
                    namespace="AWS/Diode",
                    dimensions_map={"MappingId": mapping},  # Specify the Mapping
                    metric_name="SucceededTransferSize",
                    statistic="Sum",
                    #period=Duration.days(30)
                )



            in_transit_transfer_size = cloudwatch.Metric(
                    namespace="AWS/Diode",
                    dimensions_map={"MappingId": mapping},  # Specify the Mapping
                    metric_name="InTransitTransferSize",
                    statistic="Average",
                    #period=Duration.days(1)
                )
            in_transit_transfer_count = cloudwatch.Metric(
                    namespace="AWS/Diode",
                    dimensions_map={"MappingId": mapping},  # Specify the Mapping
                    metric_name="InTransitTransferCount",
                    statistic="Average",
                   # period=Duration.days(1)
                )
            rejected_transfer_count = cloudwatch.Metric(
                namespace="AWS/Diode",
                dimensions_map={"MappingId": mapping},  # Specify the Mapping
                metric_name="RejectedTransferCount",
                statistic="Sum",
                #period=Duration.days(14)
            )
            
            
            # dashboards[mapping].add_widgets(
            #     cloudwatch.GraphWidget(
            #         title=f"Transfer Activity: Past hour",
            #         left=[transfer_created_count, succeeded_transfer_count],  # Created and Succeeded counts
            #         width=12,
            #         period=Duration.minutes(1),
            #         start='-PT1H'
            #     )
            # )
            
            
            # Create transfer activity widgets
            dashboards[mapping].add_widgets(
# SucceededTransferCount and TransferCreatedCount Statistic ‘SUM’ Period ‘Monthly’ displaying 12 months updated monthly on 1st day of month.
                cloudwatch.GraphWidget(
                    title=f"{mapping} Transfer Activity: Preceding 365 Days by month",
                    left=[transfer_created_count, succeeded_transfer_count],  # Created and Succeeded counts
                    width=12,
                    period=Duration.days(30),
                    start='-P12M'
                ),
# SucceededTransferCount and TransferCreatedCount Statistic ‘SUM’ Period ‘Daily’ displaying 14 days updated daily.
                cloudwatch.GraphWidget(
                    title=f"{mapping} Transfer Activity: Preceding 14 Days by day",
                    left=[transfer_created_count, succeeded_transfer_count],  # Created and Succeeded counts
                    width=12,
                    period=Duration.days(1),
                    start='-P14D'
                ),
# SucceededTransferCount and TransferCreatedCount Statistic ‘SUM’ Period ‘1 minute’ displaying 14 days every 5 minutes.
                cloudwatch.GraphWidget(
                    title=f"{mapping} Transfer Activity: Preceding 14 by minute",
                    left=[transfer_created_count, succeeded_transfer_count],  # Created and Succeeded counts
                    width=12,
                    period=Duration.minutes(1),
                    start='-P14D'
                ),

# SucceededTransferSize Statistic ‘SUM’ period ‘Monthly’ displaying 12 months updated monthly on 1st day of month.

                cloudwatch.GraphWidget(
                    title=f"{mapping} Transfer Size: Preceding 12 Months",
                    left=[succeeded_transfer_size],  # Succeeded size
                    width=12,
                    period=Duration.days(30),
                    start="-P12M"
                ),
# SucceededTransferSize Statistic ‘SUM’ period ‘Daily’ displaying 14 days updated daily.
                cloudwatch.GraphWidget(
                    title=f"{mapping} Transfer Size: Preceding 14 Days",
                    left=[succeeded_transfer_size],  # Succeeded size
                    width=12,
                    period=Duration.days(1),
                    start="-P14D",

                ),
# InTransitTransferSize and InTransitTransferCount Statistic ‘SUM’ Period ‘1 minute’ displaying 14 days every 5 minutes.
                cloudwatch.GraphWidget(
                    title=f"In-Transit Transfer Count: Previous 14 days",
                    left=[in_transit_transfer_count],  # In-transit size and count
                    width=12,
                    period=Duration.days(1),
                    start="-P14D"
                ),
                cloudwatch.GraphWidget(
                    title=f"In-Transit Transfer Size: Previous 14 days",
                    left=[in_transit_transfer_size],  # In-transit size and count
                    width=12,
                    period=Duration.days(1),
                    start="-P14D"
                ),
# InTransitTransferCount Statistic ‘SUM’ Period ‘Daily’ updated every 5 minutes.
                cloudwatch.GraphWidget(
                    title=f"In-Transit Transfers: Previous 1 Day by 5 minutes",
                    left=[in_transit_transfer_count],  # In-transit size and count
                    width=12,
                    period=Duration.minutes(5),
                    start="-P1D"
                ),
# SucceededTransferCount Statistic ‘SUM’ Period ‘Daily’ updated every 5 minutes.
                cloudwatch.GraphWidget(
                    title=f"Successful Transfers: Previous 1 Day by 5 minutes",
                    left=[succeeded_transfer_count],  # In-transit size and count
                    width=12,
                    period=Duration.minutes(5),
                    start="-P1D"
                ),
# FailedTransferCount Statistic ‘SUM’ Period ‘Daily’ updated every 5 minutes.
                cloudwatch.GraphWidget(
                    title=f"Failed Transfers: Previous 1 Day by 5 minutes",
                    left=[rejected_transfer_count],  # In-transit size and count
                    width=12,
                    period=Duration.minutes(5),
                    start="-P1D"
                )
            )
            # dashboards[mapping].add_widgets(
            #     cloudwatch.GraphWidget(
            #         left=[in_transit_transfer_count],
            #         title=f"{mapping} In-Transit Transfer Count - Last 12 Months",
            #         width=12,
            #         period=Duration.minutes(5),
            #         start="-P1D"
            #     ),
            #     cloudwatch.GraphWidget(
            #         left=[in_transit_transfer_size],
            #         title=f"{mapping} In-Transit Transfer Size - Last 12 Months",
            #         width=12,
            #         period=Duration.minutes(5),
            #         start="-P1D"
            #     )
            # )

            dashboards[mapping].add_widgets(
                cloudwatch.SingleValueWidget(
                    metrics=[succeeded_transfer_count],
                    title=f"Succeeded Transfer Count - Last 12 Months",
                    width=6,
                    period=Duration.days(365)
                ),
                cloudwatch.SingleValueWidget(
                    metrics=[transfer_created_count],
                    title=f"Transfer Created Count - Last 12 Months",
                    width=6,
                    period=Duration.days(365)
                ),
                cloudwatch.SingleValueWidget(
                    metrics=[succeeded_transfer_count],
                    title=f"Succeeded Transfer Count - Last 30 Days",
                    width=6,
                    period=Duration.days(30)
                ),
                cloudwatch.SingleValueWidget(
                    metrics=[transfer_created_count],
                    title=f"Transfer Created Count - Last 30 Days",
                    width=6,
                    period=Duration.days(30)
                ),
                cloudwatch.SingleValueWidget(
                    metrics=[succeeded_transfer_count],
                    title=f"Succeeded Transfer Count - Last 24 Hours",
                    width=6,
                    period=Duration.hours(24)
                ),
                cloudwatch.SingleValueWidget(
                    metrics=[transfer_created_count],
                    title=f"Transfer Created Count - Last 24 Hours",
                    width=6,
                    period=Duration.hours(24)
                ),
                cloudwatch.SingleValueWidget(
                    metrics=[rejected_transfer_count],
                    title=f"Rejected Transfer Count - Last 24 Hours",
                    width=6,
                    period=Duration.hours(24)
                ),
                cloudwatch.SingleValueWidget(
                    metrics=[rejected_transfer_count],
                    title='Rejected Transfer Count - Last 30 Days',
                    width=6,
                    period=Duration.days(30)
                ),
                cloudwatch.SingleValueWidget(
                    metrics=[rejected_transfer_count],
                    title='Rejected Transfer Count - Last 12 Months',
                    width=6,
                    period=Duration.days(365)
                )
            )