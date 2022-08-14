import os
import json
from datetime import datetime, timedelta

import boto3

REGION = "${AWS::Region}"
SERVICE = "${Service}"
CLUSTER = "${ClusterArn}"


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
    SERVICE = env("SERVICE_ARN")
    print("Test environment detected, setting REGION to", REGION)
else:
    print("REGION:", REGION)


ECS = boto3.client("ecs", region_name=REGION)
CW = boto3.client("cloudwatch", region_name=REGION)
ELB = boto3.client("elbv2", region_name=REGION)
SSM = boto3.client("ssm", region_name=REGION)


def get_idle_minutes(event):
    # return int(env("IDLE_MINUTES"))
    return event["idle_minutes"]


def get_tg_full_names(event):
    # return env_list("TG_FULL_NAMES")
    return event["target_group_names"]


def get_waiter_tg_arn(event):
    return event["waiter_tg_arn"]


def get_rule_param_name(event):
    return event["rule_param_name"]


def metric_spec(tg_full_name):
    return {
        "Namespace": "ApplicationELB",
        "MetricName": "RequestCountPerTarget",
        "Dimensions": [{"Name": "TargetGroup", "Value": tg_full_name}],
    }


def get_tg_metrics(start_time, end_time, tg_full_name):
    return CW.get_metric_statistics(
        StartTime=start_time,
        EndTime=end_time,
        Period=600,
        Statistics=["Sum"],
        **metric_spec(tg_full_name),
    )["Datapoints"]


def get_service_date():
    return ECS.describe_services(cluster=CLUSTER, services=[SERVICE])["services"][0][
        "createdAt"
    ]


def is_active(event):
    # TODO: We need to make sure the deployment isn't younger than the start_time
    minutes = get_idle_minutes(event)
    now = datetime.utcnow()
    start_time = now - timedelta(minutes=minutes)
    for tg_name in get_tg_full_names(event):
        for dp in get_tg_metrics(start_time, now, tg_name):
            if dp["Sum"] > 0:
                return True
    return False


def set_desired_count(c):
    print("Setting desiredCount of service %s to %d" % (SERVICE, c))
    res = ECS.update_service(cluster=CLUSTER, service=SERVICE, desiredCount=c)


def stash_rule_actions(event, rule_arns):
    print("Stashing rule actions")
    rules = ELB.describe_rules(RuleArns=rule_arns)["Rules"]
    SSM.put_parameter(
        Name=get_rule_param_name(event),
        Value=json.dumps(
            [{"RuleArn": r["RuleArn"], "Actions": r["Actions"]} for r in rules]
        ),
        Overwrite=True,
    )


def set_rules_to_wait(event, rule_arns):
    for rule_arn in rule_arns:
        print(f"Switching target for {rule_arn}")
        ELB.modify_rule(
            RuleArn=rule_arn,
            Actions=[
                {
                    "Type": "forward",
                    "TargetGroupArn": get_waiter_tg_arn(event),
                }
            ],
        )


def lambda_handler(event, context):
    print("event:", event)
    print(get_service_date())
    if is_active(event):
        print("Service is active. Will not shut down.")
        return

    print("Service is inactive. Shutting down.")
    set_desired_count(0)
    rule_arns = event["rule_arns"]
    stash_rule_actions(event, rule_arns)
    set_rules_to_wait(event, rule_arns)


if __name__ == "__main__":
    event = {
        "idle_minutes": 5,
        "target_group_names": ["x-Ecs-Targe-G3H44YWQYX1P/77bc0ab39459d456"],
        "rule_param_name": "CFN-AutoStopRuleParam-V7dadTeYXvGR",
        "rule_arns": [
            "arn:aws:elasticloadbalancing:us-east-1:803071473383:listener-rule/app/sig-ban-alb/5597061b6c745440/893db79165865ecb/9fb7061f85216ed7"
        ],
        "waiter_tg_arn": "arn:aws:elasticloadbalancing:us-east-1:803071473383:targetgroup/x-Ecs-AutoS-1MRGU06R489R0/375bcf65f5db1b4c",
    }
    lambda_handler(event, None)
