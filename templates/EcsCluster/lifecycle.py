import json
import yaml

from troposphere.sqs import Queue
from troposphere import Base64, GetAtt, Ref, Sub, Tags
from troposphere.autoscaling import (
    AutoScalingGroup,
    LaunchConfiguration,
    LifecycleHook,
    MetricsCollection,
    NotificationConfigurations,
)
from troposphere.iam import InstanceProfile, Policy, Role
from troposphere.logs import LogGroup
from troposphere.pipes import (
    Pipe,
    PipeTargetParameters,
    PipeTargetStateMachineParameters,
    NetworkConfiguration,
    AwsVpcConfiguration,
    PipeSourceParameters,
    DeadLetterConfig,
)
from troposphere.sns import Subscription, SubscriptionResource, Topic
from troposphere.stepfunctions import (
    StateMachine,
    LoggingConfiguration,
    LogDestination,
    CloudWatchLogsLogGroup,
)

import iam

from util import (
    TEMPLATE,
    add_export,
    add_param,
    add_resource,
    add_resource_once,
    opts_with,
    read_resource,
)


def log_group():
    return add_resource_once(
        "LifecycleLogGroup", lambda name: LogGroup(name, RetentionInDays=7)
    )


def pipe_role():
    return add_resource_once(
        "LifecyclePipeRole",
        lambda name: iam.role(
            name,
            allow={
                (
                    "sqs:ReceiveMessage",
                    "sqs:DeleteMessage",
                    "sqs:GetQueueAttributes",
                ): sqs_queue().GetAtt("Arn"),
                ("states:StartExecution",): termination_state_machine().GetAtt("Arn"),
            },
            allow_assume=[iam.PIPES_SERVICE],
            managed_policy_arns=[
                "arn:aws:iam::aws:policy/service-role/AutoScalingNotificationAccessRole"
            ],
        ),
    )


def state_machine_role():
    return add_resource_once(
        "LifecycleStateMachineRole",
        lambda name: iam.role(
            name,
            allow={
                (
                    "autoscaling:CompleteLifecycleAction",
                    "ecs:UpdateContainerInstancesState",
                    "ecs:ListContainerInstances",
                    "ecs:DescribeContainerInstances",
                    "logs:DescribeLogGroups",
                    "logs:DescribeResourcePolicies",
                    "logs:ListLogDeliveries",
                    "logs:CreateLogDelivery",
                    "logs:GetLogDelivery",
                    "logs:UpdateLogDelivery",
                    "logs:DeleteLogDelivery",
                    "logs:PutResourcePolicy",
                ): "*",
                (
                    "sqs:ReceiveMessage",
                    "sqs:DeleteMessage",
                    "sqs:GetQueueAttributes",
                ): sqs_queue().GetAtt("Arn"),
            },
            allow_assume=[iam.STATES_SERVICE],
            managed_policy_arns=[
                "arn:aws:iam::aws:policy/service-role/AutoScalingNotificationAccessRole"
            ],
        ),
    )


def termination_state_machine():
    role = state_machine_role()
    return add_resource_once(
        "LifecycleTerminationStateMachine",
        lambda name: StateMachine(
            name,
            Definition=yaml.safe_load(read_resource("TerminationStateMachine.yml")),
            DefinitionSubstitutions={
                "cluster_arn": GetAtt("EcsCluster", "Arn"),
            },
            RoleArn=GetAtt(role, "Arn"),
            LoggingConfiguration=LoggingConfiguration(
                Level="ALL",
                IncludeExecutionData=True,
                Destinations=[
                    LogDestination(
                        CloudWatchLogsLogGroup=CloudWatchLogsLogGroup(
                            LogGroupArn=log_group().GetAtt("Arn")
                        )
                    )
                ],
            ),
            DependsOn=[role],
        ),
    )


def sqs_queue():
    return add_resource_once("LifecycleSqsQueue", lambda name: Queue(name))


def pipe():
    return add_resource_once(
        "LifecyclePipe",
        lambda name: Pipe(
            name,
            Description=Sub(
                "This pipe is used by the ${AWS::StackName} ECS cluster for managing ASG lifecycle events."
            ),
            RoleArn=GetAtt(pipe_role(), "Arn"),
            Source=sqs_queue().GetAtt("Arn"),
            Target=Ref(termination_state_machine()),
            TargetParameters=PipeTargetParameters(
                StepFunctionStateMachineParameters=PipeTargetStateMachineParameters(
                    InvocationType="FIRE_AND_FORGET"
                )
            ),
        ),
    )


def sns_lambda_role():
    return add_resource_once(
        "LifecycleAutoScalingRole",
        lambda name: iam.role(
            name,
            allow_assume=[iam.AUTOSCALING_SERVICE],
            allow={
                (
                    "sqs:SendMessage",
                    "sqs:GetQueueAttributes",
                ): sqs_queue().GetAtt("Arn")
            },
            managed_policy_arns=[
                "arn:aws:iam::aws:policy/service-role/AutoScalingNotificationAccessRole"
            ],
        ),
    )


def asg_terminate_hook(asg):
    queue = sqs_queue()
    return add_resource(
        LifecycleHook(
            asg.title + "ASGTerminateHook",
            AutoScalingGroupName=Ref(asg),
            DefaultResult="ABANDON",
            HeartbeatTimeout="1800",
            LifecycleTransition="autoscaling:EC2_INSTANCE_TERMINATING",
            NotificationTargetARN=queue.GetAtt("Arn"),
            RoleARN=sns_lambda_role().GetAtt("Arn"),
            DependsOn=queue,
        )
    )


def init():
    """This is the primary entrypoint for this module and is called by main.py"""
    pipe()
