from aws_cdk import (
    Duration,
    Stack,
    aws_cloudwatch as cloudwatch,
    Aws,
)
from constructs import Construct
import json

class PipelineDashboardStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        '''
        AvScanQueue: Number of Messages Received
        AvScanQueue: Number of Message Sent
        AvScanQueue: Sent Message Size
        AvScanDLQ: Approximate Number of Message Visible
        EC2 by AutoScalingGroup: NetworkIn
        EC2 by AutoScalingGroup: NetworkOut
        Lambda: bucket-object-tagger-dev
        Lambda: bucket-object-tagger-test
        Lambda: dev-aftac-dfdl-DfdlParser
        Lambda: presigned-url-generator-test
        '''

        av_scan_queue = self.node.try_get_context("av_scan_queue_name")
        av_scan_dlq = self.node.try_get_context("av_scan_dlq_name")
        monitored_lambda_functions = self.node.try_get_context("monitored_lambda_functions")
        asg_name = self.node.try_get_context("asg_name")

        dashboard = cloudwatch.Dashboard(self, f"Pipeline-Dashboard", 
            dashboard_name=f"ValidationPipelineDashboard",
            # Inherit period from each graph
            period_override=cloudwatch.PeriodOverride.INHERIT)
        # Create Metrics
        av_scan_queue_rcvd_msgs = cloudwatch.Metric(
                namespace="AWS/SQS",
                dimensions_map={"QueueName": av_scan_queue },  
                metric_name="NumberOfMessagesReceived",
                statistic="Sum",
        )
        av_scan_queue_sent_msgs = cloudwatch.Metric(
                namespace="AWS/SQS",
                dimensions_map={"QueueName": av_scan_queue },  
                metric_name="NumberOfMessagesSent",
                statistic="Sum",
        )
        av_scan_queue_sent_msg_size = cloudwatch.Metric(
                namespace="AWS/SQS",
                dimensions_map={"QueueName": av_scan_queue },  
                metric_name="SentMessageSize",
                statistic="Sum",
        )
        av_scan_dlq_msgs_visible = cloudwatch.Metric(
                namespace="AWS/SQS",
                dimensions_map={"QueueName": av_scan_dlq },
                metric_name="ApproximateNumberOfMessagesVisible",
                statistic="Sum",
        )
        asg_network_in = cloudwatch.Metric(
                namespace="AWS/EC2",
                dimensions_map={"AutoScalingGroupName": asg_name },
                metric_name="NetworkIn",
                statistic="Sum",
        )
        asg_network_out = cloudwatch.Metric(
                namespace="AWS/EC2",
                dimensions_map={"AutoScalingGroupName": asg_name },
                metric_name="NetworkOut",
                statistic="Sum",
        )

        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title=f"Queue Messaging Widget",
                left=[av_scan_queue_rcvd_msgs, av_scan_queue_sent_msgs],  
                width=12,
                period=Duration.days(1),
                start='-P6M'
            ),
            cloudwatch.GraphWidget(
                title=f"Queue Sent Message Size Widget",
                left=[av_scan_queue_sent_msg_size],
                width=12,
                period=Duration.days(1),
                start='-P6M'
            ),
            cloudwatch.GraphWidget(
                title=f"DLQ Widget",
                left=[av_scan_dlq_msgs_visible],
                width=12,
                period=Duration.days(1),
                start='-P6M'
            ),
            cloudwatch.GraphWidget(
                title=f"ASG Network Widget",
                left=[asg_network_in, asg_network_out],
                width=12,
                period=Duration.days(1),
                start='-P6M'
            )

        )


        for function in monitored_lambda_functions:
            invocations = cloudwatch.Metric(
                namespace="AWS/Lambda",
                dimensions_map={"FunctionName": function,},
                metric_name="Invocations",
                statistic="Sum",
            )
            concurrent_executions = cloudwatch.Metric(
                namespace="AWS/Lambda",
                dimensions_map={"FunctionName": function,},
                metric_name="ConcurrentExecutions",
                statistic="Sum",
            )
            errors = cloudwatch.Metric(
                namespace="AWS/Lambda",
                dimensions_map={"FunctionName": function,},
                metric_name="Errors",
                statistic="Sum",
            )

            dashboard.add_widgets(
                cloudwatch.GraphWidget(
                    title=f"{function} Widget",
                    left=[invocations, concurrent_executions, errors],
                    width=24,
                    period=Duration.days(1),
                    start='-P6M',
                    region=Aws.REGION
                )
            )

