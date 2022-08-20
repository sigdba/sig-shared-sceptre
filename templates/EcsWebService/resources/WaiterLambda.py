import os
import json
from functools import lru_cache
from enum import Enum

import boto3

REGION = "${AWS::Region}"
CLUSTER = "${ClusterArn}"
DESIRED_COUNT = "${DesiredCount}"
STACK_ID = "${AWS::StackId}"


def env(k, default=None):
    if k in os.environ:
        ret = os.environ[k].strip()
        if len(ret) > 0:
            return ret
    if default:
        return default
    raise ValueError(f"Required environment variable {k} not set")


def env_list(k):
    return [v.strip() for v in env(k).split(",")]


# Check if we're in a test environment, and if so set the region from the
# environment or use a default.
if "AWS::Region" in REGION:
    REGION = env("AWS_DEFAULT_REGION", "us-east-1")
    CLUSTER = env("CLUSTER_ARN")
    STACK_ID = env("STACK_ID")
    DESIRED_COUNT = 1
    print("Test environment detected, setting REGION to", REGION)
else:
    print("REGION:", REGION)
    DESIRED_COUNT = int(DESIRED_COUNT)


ECS = boto3.client("ecs", region_name=REGION)
ELB = boto3.client("elbv2", region_name=REGION)
SSM = boto3.client("ssm", region_name=REGION)
CFN = boto3.client("cloudformation", region_name=REGION)


class Status(Enum):
    INITIAL = (0, "Service startup requested")
    STARTING = (1, "Service starting")
    LB_INITIAL = (2, "Checking service health")
    READY = (3, "Service ready")

    def __init__(self, order, label):
        self.order = order
        self.label = label


# We can't reference the service ARN directly because it creates a circular
# dependency in the stack. To break the dependency we look up the Service ARN
# from the stack output.
@lru_cache
def get_service_arn():
    outputs = CFN.describe_stacks(StackName=STACK_ID)["Stacks"][0]["Outputs"]
    return [o["OutputValue"] for o in outputs if o["OutputKey"] == "EcsServiceArn"][0]


def get_rule_param_name():
    return env("RULE_PARAM_NAME")


def get_rules():
    return json.loads(
        SSM.get_parameter(Name=get_rule_param_name())["Parameter"]["Value"]
    )


def get_desired_count():
    return ECS.describe_services(cluster=CLUSTER, services=[get_service_arn()])[
        "services"
    ][0]["desiredCount"]


def set_desired_count(c):
    service_arn = get_service_arn()
    print("Setting desiredCount of service %s to %d" % (service_arn, c))
    ECS.update_service(cluster=CLUSTER, service=service_arn, desiredCount=c)


def enable_real_tg(rules):
    for rule in rules:
        rule_arn = rule["RuleArn"]
        print(f"Switching target for {rule_arn}")
        ELB.modify_rule(
            RuleArn=rule_arn,
            Actions=rule["Actions"],
        )


def get_tg_arn(rule):
    for action in rule["Actions"]:
        if action["Type"] == "forward":
            tg_arn = action.get("TargetGroupArn")
            if tg_arn:
                return tg_arn
            return action["ForwardConfig"]["TargetGroups"][0]["TargetGroupArn"]
    raise ValueError(f"Target group not found for {rule}")


def get_service_status():
    if get_desired_count() < DESIRED_COUNT:
        set_desired_count(DESIRED_COUNT)
        return Status.INITIAL
    rules = get_rules()
    for rule in rules:
        healths = ELB.describe_target_health(TargetGroupArn=get_tg_arn(rule))[
            "TargetHealthDescriptions"
        ]
        if len(healths) < 1:
            return Status.STARTING

        # We can't wait for health checks because the health check won't run
        # until the TG is associated with a rule.
        #
        # for health in healths:
        #     if health["TargetHealth"]["State"] != "healthy":
        #         return Status.LB_INITIAL

    enable_real_tg(rules)
    return Status.READY


def lambda_handler(event, context):
    print("event:", event)
    status = get_service_status()
    if event["httpMethod"] != "GET":
        return {
            "statusCode": 100,
            "statusDescription": f"100 {status.value.label}",
            "headers": {"Content-Type": "text/html"},
            "body": status.label,
        }

    return {
        "statusCode": 200,
        "statusDescription": "200 OK",
        "headers": {"Content-Type": "text/html"},
        "body": f"<h1>{status.label}</h1>",
    }


if __name__ == "__main__":
    import yaml

    event = {"httpMethod": "GET"}
    print(yaml.dump(lambda_handler(event, None)))
