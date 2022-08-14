from troposphere import Ref, Sub, GetAtt, Tags
from troposphere.elasticloadbalancingv2 import (
    ListenerRule,
    TargetGroup,
    TargetDescription,
)
from troposphere.iam import Policy, Role
from troposphere.awslambda import Code, Function, Permission, Environment
from troposphere.ssm import Parameter

import json

from util import add_resource, add_resource_once, read_resource, add_depends_on


def get_target_group_full_names(template):
    return [
        GetAtt(n, "TargetGroupFullName")
        for n, o in template.resources.items()
        if type(o) is TargetGroup
    ]


def waiter_execution_role():
    return add_resource_once(
        "WaiterLambdaExecutionRole",
        lambda name: Role(
            name,
            Policies=[
                Policy(
                    PolicyName="lambda-inline",
                    PolicyDocument={
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Effect": "Allow",
                                "Action": [
                                    "logs:CreateLogGroup",
                                    "logs:CreateLogStream",
                                    "logs:PutLogEvents",
                                ],
                                "Resource": "*",
                            },
                            {
                                "Effect": "Allow",
                                "Action": ["ecs:DescribeServices"],
                                "Resource": Ref("Service"),
                            },
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
        ),
    )


def add_rules_param():
    return add_resource(Parameter("AutoStopRuleParam", Type="String", Value="NONE"))


def add_waiter_lambda(as_conf, template):
    exec_role = waiter_execution_role()
    rules_param = add_rules_param()
    return add_resource_once(
        "WaiterLambdaFn",
        lambda name: Function(
            name,
            Description="Presents a 'please wait' page while restarting a service.",
            # TODO: VPCConfig?
            Handler="index.lambda_handler",
            Role=GetAtt(exec_role, "Arn"),
            Runtime="python3.9",
            MemorySize=128,
            Timeout=900,
            Code=Code(ZipFile=Sub(read_resource("WaiterLambda.py"))),
            Environment=Environment(Variables={"RULES_PARAM": Ref(rules_param)}),
        ),
    )


def waiter_invoke_permission(fn):
    return add_resource(
        Permission(
            "WaiterLambdaInvokePermission",
            FunctionName=GetAtt(fn, "Arn"),
            Action="lambda:InvokeFunction",
            Principal="elasticloadbalancing.amazonaws.com",
        )
    )


def add_waiter_tg(as_conf, template):
    waiter_lambda = add_waiter_lambda(as_conf, template)
    invoke_perm = waiter_invoke_permission(waiter_lambda)
    return add_resource(
        TargetGroup(
            "AutoStopWaiterTg",
            TargetType="lambda",
            Targets=[TargetDescription(Id=GetAtt(waiter_lambda, "Arn"))],
            Tags=Tags(Name=Sub("${AWS::StackName} Waiter")),
            DependsOn=[invoke_perm.title],
        )
    )


def add_autostop(user_data, template):
    target_group_titles = get_target_group_full_names(template)

    waiter_tg = add_waiter_tg(user_data.auto_stop, template)
    # for n, o in template.resources.items():
    #     if type(o) is TargetGroup:
    #         add_depends_on(o, "AutoStopWaiterTg")
