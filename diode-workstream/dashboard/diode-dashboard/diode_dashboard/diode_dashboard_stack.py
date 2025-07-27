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

        # Get the mission areas and mappings from context
        mission_mappings = self.node.try_get_context("mapping_ids")
        print(mission_mappings)
        
        dashboard_mappings = []
        dashboards = {}
        
        # Maximum mappings per dashboard
        list_size = 5
        dashboard_counter = 1
        
        # Process each mission area
        for mission_area, mapping_dict in mission_mappings.items():
            # Get all mappings for this mission area
            friendly_to_mapping_id = mapping_dict
            
            # Break mappings into chunks of 5
            mapping_chunks = []
            current_chunk = {}
            count = 0
            
            for friendly_name, mapping_id in friendly_to_mapping_id.items():
                if count >= list_size:
                    mapping_chunks.append(current_chunk)
                    current_chunk = {}
                    count = 0
                
                current_chunk[friendly_name] = mapping_id
                count += 1
                
            # Add the last chunk if it contains any mappings
            if current_chunk:
                mapping_chunks.append(current_chunk)
            
            # Create dashboards for each chunk
            for chunk_index, mapping_chunk in enumerate(mapping_chunks):
                # Create dashboard name based on mission area and chunk index if needed
                dashboard_name = f"{mission_area}-Dashboard"
                if len(mapping_chunks) > 1:
                    dashboard_name = f"{mission_area}-Dashboard-{chunk_index+1}"
                
                # Store the mapping information for this dashboard
                dashboard_mappings.append({dashboard_name: mapping_chunk})
                
                # Create CloudWatch Dashboard
                dashboard = cloudwatch.Dashboard(
                    self, 
                    f"DiodeMonitoring-{dashboard_name}", 
                    dashboard_name=dashboard_name,
                    period_override=cloudwatch.PeriodOverride.INHERIT
                )
                dashboards[str(dashboard_counter)] = dashboard
                
                # Collect all metrics for all mappings in this dashboard
                all_transfer_created_count = []
                all_succeeded_transfer_count = []
                all_succeeded_transfer_size = []
                all_in_transit_transfer_size = []
                all_in_transit_transfer_count = []
                all_rejected_transfer_count = []

                # Define the metrics for each mapping
                for friendly_name, mapping_id in mapping_chunk.items():
                    # Create metrics with friendly names as labels
                    transfer_created_count = cloudwatch.Metric(
                        namespace="AWS/Diode",
                        dimensions_map={"MappingId": mapping_id},
                        metric_name="TransferCreatedCount",
                        statistic="Sum",
                        label=f"{friendly_name} - TransferCreatedCount"  # Use friendly name
                    )
                    succeeded_transfer_count = cloudwatch.Metric(
                        namespace="AWS/Diode",
                        dimensions_map={"MappingId": mapping_id},
                        metric_name="SucceededTransferCount",
                        statistic="Sum",
                        label=f"{friendly_name} - SucceededTransferCount"
                    )
                    succeeded_transfer_size = cloudwatch.Metric(
                        namespace="AWS/Diode",
                        dimensions_map={"MappingId": mapping_id},
                        metric_name="SucceededTransferSize",
                        statistic="Sum",
                        label=f"{friendly_name} - SucceededTransferSize"
                    )
                    in_transit_transfer_size = cloudwatch.Metric(
                        namespace="AWS/Diode",
                        dimensions_map={"MappingId": mapping_id},
                        metric_name="InTransitTransferSize",
                        statistic="Average",
                        label=f"{friendly_name} - InTransitTransferSize"
                    )
                    in_transit_transfer_count = cloudwatch.Metric(
                        namespace="AWS/Diode",
                        dimensions_map={"MappingId": mapping_id},
                        metric_name="InTransitTransferCount",
                        statistic="Average",
                        label=f"{friendly_name} - InTransitTransferCount"
                    )
                    rejected_transfer_count = cloudwatch.Metric(
                        namespace="AWS/Diode",
                        dimensions_map={"MappingId": mapping_id},
                        metric_name="RejectedTransferCount",
                        statistic="Sum",
                        label=f"{friendly_name} - RejectedTransferCount"
                    )
                    
                    # Add metrics to their respective lists
                    all_transfer_created_count.append(transfer_created_count)
                    all_succeeded_transfer_count.append(succeeded_transfer_count)
                    all_succeeded_transfer_size.append(succeeded_transfer_size)
                    all_in_transit_transfer_size.append(in_transit_transfer_size)
                    all_in_transit_transfer_count.append(in_transit_transfer_count)
                    all_rejected_transfer_count.append(rejected_transfer_count)

                # Create widgets for this dashboard
                dashboard.add_widgets(
                    # Transfer Activity widgets with all mappings overlaid
                    cloudwatch.GraphWidget(
                        title=f"{mission_area} Transfer Activity: Preceding 365 Days by month",
                        left=all_transfer_created_count + all_succeeded_transfer_count,
                        width=12,
                        period=Duration.days(30),
                        start='-P12M'
                    ),
                    cloudwatch.GraphWidget(
                        title=f"{mission_area} Transfer Activity: Preceding 14 Days by day",
                        left=all_transfer_created_count + all_succeeded_transfer_count,
                        width=12,
                        period=Duration.days(1),
                        start='-P14D'
                    ),
                    cloudwatch.GraphWidget(
                        title=f"{mission_area} Transfer Activity: Preceding 14 days by minute",
                        left=all_transfer_created_count + all_succeeded_transfer_count,
                        width=12,
                        period=Duration.minutes(1),
                        start='-P14D'
                    ),
                    
                    # Transfer Size widgets
                    cloudwatch.GraphWidget(
                        title=f"{mission_area} Transfer Size: Preceding 12 Months",
                        left=all_succeeded_transfer_size,
                        width=12,
                        period=Duration.days(30),
                        start="-P12M"
                    ),
                    cloudwatch.GraphWidget(
                        title=f"{mission_area} Transfer Size: Preceding 14 Days",
                        left=all_succeeded_transfer_size,
                        width=12,
                        period=Duration.days(1),
                        start="-P14D",
                    ),
                    
                    # In-Transit widgets
                    cloudwatch.GraphWidget(
                        title=f"{mission_area} In-Transit Transfer Count: Previous 14 days",
                        left=all_in_transit_transfer_count,
                        width=12,
                        period=Duration.days(1),
                        start="-P14D"
                    ),
                    cloudwatch.GraphWidget(
                        title=f"{mission_area} In-Transit Transfer Size: Previous 14 days",
                        left=all_in_transit_transfer_size,
                        width=12,
                        period=Duration.days(1),
                        start="-P14D"
                    ),
                    cloudwatch.GraphWidget(
                        title=f"{mission_area} In-Transit Transfers: Previous 1 Day by 5 minutes",
                        left=all_in_transit_transfer_count,
                        width=12,
                        period=Duration.minutes(5),
                        start="-P1D"
                    ),
                    cloudwatch.GraphWidget(
                        title=f"{mission_area} Successful Transfers: Previous 1 Day by 5 minutes",
                        left=all_succeeded_transfer_count,
                        width=12,
                        period=Duration.minutes(5),
                        start="-P1D"
                    ),
                    cloudwatch.GraphWidget(
                        title=f"{mission_area} Failed Transfers: Previous 1 Day by 5 minutes",
                        left=all_rejected_transfer_count,
                        width=12,
                        period=Duration.minutes(5),
                        start="-P1D"
                    )
                )

                # Single value widgets for each mapping using friendly names
                single_value_widgets = []
                for i, (friendly_name, _) in enumerate(mapping_chunk.items()):
                    single_value_widgets.extend([
                        cloudwatch.SingleValueWidget(
                            metrics=[all_succeeded_transfer_count[i]],
                            title=f"{friendly_name} Succeeded - Last 12 Months",
                            width=6,
                            period=Duration.days(365)
                        ),
                        cloudwatch.SingleValueWidget(
                            metrics=[all_transfer_created_count[i]],
                            title=f"{friendly_name} Created - Last 12 Months",
                            width=6,
                            period=Duration.days(365)
                        ),
                    ])
                
                dashboard.add_widgets(*single_value_widgets)
                dashboard_counter += 1
        
        print(dashboard_mappings)
        
        # Store the complete mapping structure in SSM Parameter Store
        ssm.StringParameter(
            self,
            "CompleteDashboardMappings",
            parameter_name="/diode/dashboards/complete-mappings",
            string_value=json.dumps(dashboard_mappings),
            description="Complete mapping of all dashboards to their mapping IDs and friendly names"
        )