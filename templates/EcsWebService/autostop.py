import yaml
from troposphere import GetAtt, Join, Ref, Sub, Tags
from troposphere.awslambda import (
    Code,
    DeadLetterConfig,
    Environment,
    Function,
    Permission,
)
from troposphere.elasticloadbalancingv2 import (
    ListenerRule,
    TargetDescription,
    TargetGroup,
)
from troposphere.events import Rule as EventRule
from troposphere.events import Target as EventTarget
from troposphere.iam import PolicyType, Role
from troposphere.logs import LogGroup
from troposphere.ssm import Parameter
from troposphere.stepfunctions import (
    CloudWatchLogsLogGroup as SmLogGroup,
    LogDestination as SmLogDest,
    LoggingConfiguration as SmLoggingConf,
    StateMachine,
)

from util import (
    add_depends_on,
    add_output,
    add_resource,
    add_resource_once,
    opts_with,
    read_resource,
)

#
# The "rules parameter" is an SSM parameter used to store the original actions
# for the listener rule. When the service is stopped, the rule's actions are
# "stashed" in this parameter. When the service is restarted, the actions are
# "restored" to the listener rule.
#


def add_rules_param():
    return add_resource(Parameter("AutoStopRuleParam", Type="String", Value="NONE"))


def add_sns_publish_policy(topic_arn):
    return add_resource_once(
        "AutoStopSnsPublishPolicy",
        lambda name: PolicyType(
            name,
            PolicyName="AutoStopSnsPublish",
            Roles=[
                Ref("StarterLambdaExecutionRole"),
                Ref("StopperLambdaExecutionRole"),
            ],
            PolicyDocument={
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": ["sns:Publish"],
                        "Resource": topic_arn,
                    }
                ],
            },
        ),
    )


#
# The "starter" is a Step Function whose job is to start the service, wait for
# it to come up, then restore the original actions to the listener rule.
#


def starter_execution_role():
    return add_resource_once(
        "StarterLambdaExecutionRole",
        lambda name: Role(
            name,
            Policies=[],
            AssumeRolePolicyDocument={
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"Service": ["states.amazonaws.com"]},
                        "Action": ["sts:AssumeRole"],
                    }
                ],
            },
            ManagedPolicyArns=[],
            Path="/",
        ),
    )


# Since stopping is the inverse of starting, this policy is used by both starter
# and stopper.
def starter_execution_policy(rule_names):
    return add_resource_once(
        "StarterLambdaExecutionRolePolicy",
        lambda name: PolicyType(
            name,
            PolicyName="lambda-inline",
            Roles=[
                Ref("StarterLambdaExecutionRole"),
                Ref("StopperLambdaExecutionRole"),
            ],
            PolicyDocument={
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "logs:CreateLogGroup",
                            "logs:CreateLogStream",
                            "logs:PutLogEvents",
                            "logs:CreateLogDelivery",
                            "logs:GetLogDelivery",
                            "logs:UpdateLogDelivery",
                            "logs:DeleteLogDelivery",
                            "logs:ListLogDeliveries",
                            "logs:PutResourcePolicy",
                            "logs:DescribeResourcePolicies",
                            "logs:DescribeLogGroups",
                            "ecs:DescribeServices",
                            "elasticloadbalancing:DescribeRules",
                            "elasticloadbalancing:DescribeTargetHealth",
                            "cloudwatch:GetMetricStatistics",
                        ],
                        "Resource": "*",
                    },
                    {
                        "Effect": "Allow",
                        "Action": ["cloudformation:DescribeStacks"],
                        "Resource": Ref("AWS::StackId"),
                    },
                    {
                        "Effect": "Allow",
                        "Action": ["ssm:GetParameter", "ssm:PutParameter"],
                        "Resource": Sub(
                            "arn:${AWS::Partition}:ssm:${AWS::Region}:${AWS::AccountId}:parameter/${AutoStopRuleParam}"
                        ),
                    },
                    {
                        "Effect": "Allow",
                        "Action": ["elasticloadbalancing:ModifyRule"],
                        "Resource": [GetAtt(n, "RuleArn") for n in rule_names],
                    },
                    {
                        "Effect": "Allow",
                        "Action": ["ecs:UpdateService"],
                        "Resource": Ref("Service"),
                    },
                    {
                        "Effect": "Allow",
                        "Action": ["events:EnableRule", "events:DisableRule"],
                        "Resource": GetAtt("AutoStopScheduleRule", "Arn"),
                    },
                ],
            },
        ),
    )


def add_starter_log_group():
    return add_resource_once(
        "StarterStateMachineLogGroup", lambda name: LogGroup(name, RetentionInDays=7)
    )


def add_starter_state_machine():
    return add_resource_once(
        "StarterStateMachine",
        lambda name: StateMachine(
            name,
            Definition=yaml.safe_load(read_resource("StartStateMachine.yaml")),
            RoleArn=GetAtt("StarterLambdaExecutionRole", "Arn"),
            LoggingConfiguration=SmLoggingConf(
                Level="ALL",
                IncludeExecutionData=True,
                Destinations=[
                    SmLogDest(
                        CloudWatchLogsLogGroup=SmLogGroup(
                            LogGroupArn=GetAtt(add_starter_log_group(), "Arn")
                        )
                    )
                ],
            ),
            DependsOn=["StarterLambdaExecutionRolePolicy"],
        ),
    )


#
# The "waiter" is a Lambda function. When the service is auto-stopped, the
# listener rule(s) are updated to direct traffic to the waiter function. When a
# user browses to the service URL the waiter initiates the "starter" (above) and
# presents the user with a "please wait" page which auto-refreshes.
#


def waiter_execution_role():
    return add_resource_once(
        "WaiterLambdaExecutionRole",
        lambda name: Role(
            name,
            Policies=[],
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


def waiter_execution_policy(role):
    return add_resource_once(
        "WaiterLambdaExecutionRolePolicy",
        lambda name: PolicyType(
            name,
            PolicyName="lambda-inline",
            Roles=[Ref(role)],
            PolicyDocument={
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "logs:CreateLogGroup",
                            "logs:CreateLogStream",
                            "logs:PutLogEvents",
                            "ecs:DescribeServices",
                            "elasticloadbalancing:DescribeTargetHealth",
                        ],
                        "Resource": "*",
                    },
                    {
                        "Effect": "Allow",
                        "Action": ["cloudformation:DescribeStacks"],
                        "Resource": Ref("AWS::StackId"),
                    },
                    {
                        "Effect": "Allow",
                        "Action": ["states:ListExecutions", "states:StartExecution"],
                        "Resource": Ref("StarterStateMachine"),
                    },
                    {
                        "Effect": "Allow",
                        "Action": ["ssm:GetParameter"],
                        "Resource": Sub(
                            "arn:${AWS::Partition}:ssm:${AWS::Region}:${AWS::AccountId}:parameter/${AutoStopRuleParam}"
                        ),
                    },
                ],
            },
        ),
    )


def add_waiter_lambda(as_conf, exec_role):
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
            Environment=Environment(
                Variables={
                    "RULE_PARAM_NAME": Ref(rules_param),
                    "REFRESH_SECONDS": as_conf.waiter_refresh_seconds,
                    "USER_CSS": as_conf.waiter_css,
                    "PAGE_TITLE": as_conf.waiter_page_title or Ref("AWS::StackName"),
                    "HEADING": as_conf.waiter_heading,
                    "EXPLANATION": as_conf.waiter_explanation,
                }
            ),
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


def add_waiter_tg(as_conf, exec_role):
    waiter_lambda = add_waiter_lambda(as_conf, exec_role)
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


#
# The "stopper" is a Lambda function which runs on a schedule in Event Bridge.
# When fired it checks to see if the service has meets the "idle" threshold. If
# so, it redirects traffic to the "waiter" by updating the listener rule then
# stops the service.
#


def add_stopper_execution_role():
    return add_resource_once(
        "StopperLambdaExecutionRole",
        lambda name: Role(
            name,
            Policies=[],
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


def add_stopper_lambda(as_conf):
    return add_resource_once(
        "StopperLambdaFn",
        lambda name: Function(
            name,
            Description="Polls TG metrics and auto-stops idle ECS service.",
            Handler="index.lambda_handler",
            Role=GetAtt("StopperLambdaExecutionRole", "Arn"),
            Runtime="python3.9",
            MemorySize=128,
            Timeout=900,
            Code=Code(ZipFile=Sub(read_resource("StopLambda.py"))),
            **opts_with(
                DeadLetterConfig=(
                    as_conf.alert_topic_arn,
                    lambda arn: DeadLetterConfig(TargetArn=arn),
                ),
                DependsOn=(
                    as_conf.alert_topic_arn,
                    lambda _: ["AutoStopSnsPublishPolicy"],
                ),
            )
        ),
    )


def add_stopper_invoke_permission(fn):
    return add_resource(
        Permission(
            "StopperLambdaInvokePermission",
            FunctionName=GetAtt(fn, "Arn"),
            Action="lambda:InvokeFunction",
            Principal="events.amazonaws.com",
        )
    )


def add_stopper_scheduling_rule(as_conf, tg_names, rule_names):
    return add_resource(
        EventRule(
            "AutoStopScheduleRule",
            ScheduleExpression=as_conf.idle_check_schedule,
            Description=Sub("Auto-stop check for ${AWS::StackName}"),
            Targets=[
                EventTarget(
                    Id="ScheduleRule",
                    Arn=GetAtt("StopperLambdaFn", "Arn"),
                    Input=Sub(
                        """{
                            "idle_minutes": ${idle_minutes},
                            "target_group_names": ["${tg_names}"],
                            "rule_param_name": "${param_name}",
                            "rule_arns": ["${rule_arns}"],
                            "waiter_tg_arn": "${waiter_tg_arn}"
                        }""",
                        idle_minutes=as_conf.idle_minutes,
                        tg_names=Join(
                            '","', [GetAtt(n, "TargetGroupFullName") for n in tg_names]
                        ),
                        param_name=Ref("AutoStopRuleParam"),
                        rule_arns=Join('","', [Ref(n) for n in rule_names]),
                        waiter_tg_arn=Ref("AutoStopWaiterTg"),
                    ),
                )
            ],
        )
    )


def add_autostop(user_data, template):
    # TODO: Can the whole autostart process be represented as a step function?
    #       The advantages are that the state would always be unambiguous and we
    #       might not need to "stash" the action list in a parameter.

    rule_names = [n for n, o in template.resources.items() if type(o) is ListenerRule]
    if len(rule_names) < 1:
        raise ValueError(
            "Auto-stop feature cannot be used on a service with no load-balancer rules."
        )

    tg_names = [n for n, o in template.resources.items() if type(o) is TargetGroup]
    if len(tg_names) < 1:
        raise ValueError(
            "Auto-stop feature cannot be used on a service with no target groups."
        )

    if user_data.auto_stop.alert_topic_arn:
        add_sns_publish_policy(user_data.auto_stop.alert_topic_arn)

    starter_execution_role()
    starter_execution_policy(rule_names)
    starter = add_starter_state_machine()
    add_output("StarterStateMachineArn", Ref(starter))

    waiter_exec_role = waiter_execution_role()
    waiter_execution_policy(waiter_exec_role)
    waiter_tg = add_waiter_tg(user_data.auto_stop, waiter_exec_role)

    add_stopper_execution_role()
    stopper_fn = add_stopper_lambda(user_data.auto_stop)
    add_stopper_invoke_permission(stopper_fn)

    schedule_rule = add_stopper_scheduling_rule(
        user_data.auto_stop, tg_names, rule_names
    )
    add_output("StopperScheduleRuleName", Ref(schedule_rule))

    for n, o in template.resources.items():
        if type(o) is ListenerRule:
            add_depends_on(o, waiter_tg.title)
