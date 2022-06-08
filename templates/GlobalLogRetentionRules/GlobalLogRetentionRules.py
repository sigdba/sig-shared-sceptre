import hashlib
import os.path
import json

from troposphere import Template, Ref, Sub, GetAtt
from troposphere.awslambda import Permission, Function, Code
from troposphere.events import Rule as EventRule, Target as EventTarget
from troposphere.iam import Role, Policy

from model import UserDataModel

TEMPLATE = Template()
PRIORITY_CACHE = []


def read_local_file(path):
    with open(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), path), "r"
    ) as fp:
        return fp.read()


def add_resource(r):
    TEMPLATE.add_resource(r)
    return r


def clean_title(s):
    return (
        s.replace("-", "DASH")
        .replace(".", "DOT")
        .replace("_", "US")
        .replace("*", "STAR")
        .replace("?", "QM")
        .replace("/", "SLASH")
        .replace(" ", "SP")
    )


def md5(s):
    return hashlib.md5(s.encode("utf-8")).hexdigest()


def lambda_execution_role():
    return add_resource(
        Role(
            "LambdaExecutionRole",
            Policies=[
                Policy(
                    PolicyName="lambda-inline",
                    PolicyDocument={
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Effect": "Allow",
                                "Action": [
                                    "autoscaling:CompleteLifecycleAction",
                                    "logs:CreateLogGroup",
                                    "logs:CreateLogStream",
                                    "logs:PutLogEvents",
                                    "logs:PutRetentionPolicy",
                                    "logs:DescribeLogGroups",
                                ],
                                "Resource": "*",
                            }
                        ],
                    },
                )
            ],
            AssumeRolePolicyDocument={
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"Service": ["lambda.amazonaws.com"]},
                        "Action": ["sts:AssumeRole"],
                    }
                ],
            },
            ManagedPolicyArns=[],
            Path="/",
        )
    )


def lambda_function():
    return add_resource(
        Function(
            "LambdaFunction",
            Description="Sets CloudWatch log retentions based on rules",
            Handler="index.lambda_handler",
            Role=GetAtt("LambdaExecutionRole", "Arn"),
            Runtime="python3.6",
            MemorySize=128,
            Timeout=60,
            Code=Code(
                ZipFile=Sub(read_local_file("GlobalLogRetentionRules_Lambda.py"))
            ),
        )
    )


def lambda_invoke_permission():
    return add_resource(
        Permission(
            "LambdaInvokePermission",
            FunctionName=Ref("LambdaFunction"),
            Action="lambda:InvokeFunction",
            Principal="events.amazonaws.com",
            SourceArn=GetAtt("ScheduleRule", "Arn"),
        )
    )


def scheduling_rule(schedule_expr, rules):
    return add_resource(
        EventRule(
            "ScheduleRule",
            ScheduleExpression=schedule_expr,
            Targets=[
                EventTarget(
                    Id="Lambda",
                    Arn=GetAtt("LambdaFunction", "Arn"),
                    Input=json.dumps({"rules": rules}),
                )
            ],
        )
    )


def sceptre_handler(sceptre_user_data):
    if sceptre_user_data is None:
        # We're generating documetation. Return the template with just parameters.
        return TEMPLATE
    # Validate user input
    # TODO: Update code to use pydantic model instead of just validating
    UserDataModel.parse_obj(sceptre_user_data)

    lambda_execution_role()
    lambda_function()
    lambda_invoke_permission()
    scheduling_rule(
        sceptre_user_data.get("schedule", "rate(1 day)"), sceptre_user_data["rules"]
    )
    return TEMPLATE.to_json()
