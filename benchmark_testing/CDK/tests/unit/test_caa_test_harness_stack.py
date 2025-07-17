import aws_cdk as core
import aws_cdk.assertions as assertions

from caa_test_harness.caa_test_harness_stack import CaaTestHarnessStack


# example tests. To run these tests, uncomment this file along with the example
# resource in caa_test_harness/caa_test_harness_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = CaaTestHarnessStack(app, "caa-test-harness")
    template = assertions.Template.from_stack(stack)


#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
