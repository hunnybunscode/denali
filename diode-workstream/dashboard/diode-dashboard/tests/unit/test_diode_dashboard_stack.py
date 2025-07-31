import aws_cdk as core
import aws_cdk.assertions as assertions

from diode_dashboard.diode_dashboard_stack import DiodeDashboardStack

# example tests. To run these tests, uncomment this file along with the example
# resource in diode_dashboard/diode_dashboard_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = DiodeDashboardStack(app, "diode-dashboard")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
