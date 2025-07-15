from aws_cdk import (
    Duration,
    Stack,
    aws_cloudwatch as cloudwatch,
    aws_ssm as ssm,
)
from constructs import Construct
import json

class DashboardStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        mapping_ids = self.node.try_get_context("mapping_ids")
        print(mapping_ids)
        
        dashboard_mappings = []
        dashboards = {}
        # break list of mappings into multiple lists of 5 to ensure that each dashboard does not contain too much information
        list_size = 5
        my_mappings = [mapping_ids[i:i+list_size] for i in range(0,len(mapping_ids),5)]
        iterator = 1 
        db_iterator = 1
        
        for mapping_ids_subset in my_mappings:
            dashboard_mappings.append({f"DiodeMonitoring-Dashboard-{str(db_iterator)}": mapping_ids_subset})
            
            # Create a CloudWatch Dashboard
            dashboards[str(iterator)] = cloudwatch.Dashboard(self, f"DiodeMonitoring-Dashboard-{str(db_iterator)}", 
                dashboard_name=f"DiodeMonitoring-Dashboard-{str(db_iterator)}",
                # Inherit period from each graph
                period_override=cloudwatch.PeriodOverride.INHERIT)

            # Collect all metrics for all mappings in this dashboard
            all_transfer_created_count = []
            all_succeeded_transfer_count = []
            all_succeeded_transfer_size = []
            all_in_transit_transfer_size = []
            all_in_transit_transfer_count = []
            all_rejected_transfer_count = []

            # Define the metrics for each mapping
            for mapping in mapping_ids_subset:
                transfer_created_count = cloudwatch.Metric(
                    namespace="AWS/Diode",
                    dimensions_map={"MappingId": mapping},
                    metric_name="TransferCreatedCount",
                    statistic="Sum",
                    label=f"{mapping} - TransferCreatedCount"  # Add label to distinguish in the graph
                )
                succeeded_transfer_count = cloudwatch.Metric(
                    namespace="AWS/Diode",
                    dimensions_map={"MappingId": mapping},
                    metric_name="SucceededTransferCount",
                    statistic="Sum",
                    label=f"{mapping} - SucceededTransferCount"
                )
                succeeded_transfer_size = cloudwatch.Metric(
                    namespace="AWS/Diode",
                    dimensions_map={"MappingId": mapping},
                    metric_name="SucceededTransferSize",
                    statistic="Sum",
                    label=f"{mapping} - SucceededTransferSize"
                )
                in_transit_transfer_size = cloudwatch.Metric(
                    namespace="AWS/Diode",
                    dimensions_map={"MappingId": mapping},
                    metric_name="InTransitTransferSize",
                    statistic="Average",
                    label=f"{mapping} - InTransitTransferSize"
                )
                in_transit_transfer_count = cloudwatch.Metric(
                    namespace="AWS/Diode",
                    dimensions_map={"MappingId": mapping},
                    metric_name="InTransitTransferCount",
                    statistic="Average",
                    label=f"{mapping} - InTransitTransferCount"
                )
                rejected_transfer_count = cloudwatch.Metric(
                    namespace="AWS/Diode",
                    dimensions_map={"MappingId": mapping},
                    metric_name="RejectedTransferCount",
                    statistic="Sum",
                    label=f"{mapping} - RejectedTransferCount"
                )
                
                # Add metrics to their respective lists
                all_transfer_created_count.append(transfer_created_count)
                all_succeeded_transfer_count.append(succeeded_transfer_count)
                all_succeeded_transfer_size.append(succeeded_transfer_size)
                all_in_transit_transfer_size.append(in_transit_transfer_size)
                all_in_transit_transfer_count.append(in_transit_transfer_count)
                all_rejected_transfer_count.append(rejected_transfer_count)

            # Create widgets with all metrics overlaid (outside the mapping loop)
            dashboards[str(iterator)].add_widgets(
                # Transfer Activity widgets with all mappings overlaid
                cloudwatch.GraphWidget(
                    title=f"All Mappings Transfer Activity: Preceding 365 Days by month",
                    left=all_transfer_created_count + all_succeeded_transfer_count,
                    width=12,
                    period=Duration.days(30),
                    start='-P12M'
                ),
                cloudwatch.GraphWidget(
                    title=f"All Mappings Transfer Activity: Preceding 14 Days by day",
                    left=all_transfer_created_count + all_succeeded_transfer_count,
                    width=12,
                    period=Duration.days(1),
                    start='-P14D'
                ),
                cloudwatch.GraphWidget(
                    title=f"All Mappings Transfer Activity: Preceding 14 by minute",
                    left=all_transfer_created_count + all_succeeded_transfer_count,
                    width=12,
                    period=Duration.minutes(1),
                    start='-P14D'
                ),
                
                # Transfer Size widgets
                cloudwatch.GraphWidget(
                    title=f"All Mappings Transfer Size: Preceding 12 Months",
                    left=all_succeeded_transfer_size,
                    width=12,
                    period=Duration.days(30),
                    start="-P12M"
                ),
                cloudwatch.GraphWidget(
                    title=f"All Mappings Transfer Size: Preceding 14 Days",
                    left=all_succeeded_transfer_size,
                    width=12,
                    period=Duration.days(1),
                    start="-P14D",
                ),
                
                # In-Transit widgets
                cloudwatch.GraphWidget(
                    title=f"All Mappings In-Transit Transfer Count: Previous 14 days",
                    left=all_in_transit_transfer_count,
                    width=12,
                    period=Duration.days(1),
                    start="-P14D"
                ),
                cloudwatch.GraphWidget(
                    title=f"All Mappings In-Transit Transfer Size: Previous 14 days",
                    left=all_in_transit_transfer_size,
                    width=12,
                    period=Duration.days(1),
                    start="-P14D"
                ),
                cloudwatch.GraphWidget(
                    title=f"All Mappings In-Transit Transfers: Previous 1 Day by 5 minutes",
                    left=all_in_transit_transfer_count,
                    width=12,
                    period=Duration.minutes(5),
                    start="-P1D"
                ),
                cloudwatch.GraphWidget(
                    title=f"All Mappings Successful Transfers: Previous 1 Day by 5 minutes",
                    left=all_succeeded_transfer_count,
                    width=12,
                    period=Duration.minutes(5),
                    start="-P1D"
                ),
                cloudwatch.GraphWidget(
                    title=f"All Mappings Failed Transfers: Previous 1 Day by 5 minutes",
                    left=all_rejected_transfer_count,
                    width=12,
                    period=Duration.minutes(5),
                    start="-P1D"
                )
            )

            # For SingleValueWidgets, you might want to create separate widgets for each mapping
            # or create aggregated widgets. Here's an example of separate widgets:
            single_value_widgets = []
            for i, mapping in enumerate(mapping_ids_subset):
                single_value_widgets.extend([
                    cloudwatch.SingleValueWidget(
                        metrics=[all_succeeded_transfer_count[i]],
                        title=f"{mapping} Succeeded - Last 12 Months",
                        width=6,
                        period=Duration.days(365)
                    ),
                    cloudwatch.SingleValueWidget(
                        metrics=[all_transfer_created_count[i]],
                        title=f"{mapping} Created - Last 12 Months",
                        width=6,
                        period=Duration.days(365)
                    ),
                ])
            
            dashboards[str(iterator)].add_widgets(*single_value_widgets)
            
            iterator += 1
            db_iterator += 1
            
        print(dashboard_mappings)
        # Optional: Store the complete mapping structure as a single parameter
        complete_mapping = {}
        for dashboard_mapping in dashboard_mappings:
            complete_mapping.update(dashboard_mapping)

        ssm.StringParameter(
            self,
            "CompleteDashboardMappings",
            parameter_name="/diode/dashboards/complete-mappings",
            string_value=json.dumps(complete_mapping),
            description="Complete mapping of all dashboards to their mapping IDs"
        )