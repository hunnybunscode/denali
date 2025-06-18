import aws_cdk as core
import aws_cdk.assertions as assertions

from ai_ml_workstream.ai_ml_workstream_stack import AiMlWorkstreamStack

# example tests. To run these tests, uncomment this file along with the example
# resource in ai_ml_workstream/ai_ml_workstream_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = AiMlWorkstreamStack(app, "ai-ml-workstream")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
