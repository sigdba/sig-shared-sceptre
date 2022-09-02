import os
from datetime import datetime, timedelta, timezone

import boto3

REGION = "${AWS::Region}"
SERVICE = "${Service}"
CLUSTER = "${ClusterArn}"
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
    SERVICE = env("SERVICE_ARN")
    print("Test environment detected, setting REGION to", REGION)
else:
    print("REGION:", REGION)


ECS = boto3.client("ecs", region_name=REGION)
CW = boto3.client("cloudwatch", region_name=REGION)
ELB = boto3.client("elbv2", region_name=REGION)
CFN = boto3.client("cloudformation", region_name=REGION)
EB = boto3.client("events", region_name=REGION)


def get_idle_minutes(event):
    return event["idle_minutes"]


def get_tg_full_names(event):
    return event["target_group_names"]


def get_waiter_tg_arn(event):
    return event["waiter_tg_arn"]


def get_rule_skipper_key(event):
    return event["rule_skipper_key"]


def describe_stack():
    return CFN.describe_stacks(StackName=STACK_ID)["Stacks"][0]


def get_schedule_rule_name():
    outputs = describe_stack()["Outputs"]
    return [
        o["OutputValue"] for o in outputs if o["OutputKey"] == "StopperScheduleRuleName"
    ][0]


def is_stack_updating():
    status = describe_stack()["StackStatus"]
    print("Stack status:", status)
    return not status.endswith("_COMPLETE")


def metric_spec(tg_full_name):
    return {
        "Namespace": "AWS/ApplicationELB",
        "MetricName": "RequestCountPerTarget",
        "Dimensions": [{"Name": "TargetGroup", "Value": tg_full_name}],
    }


def get_tg_metrics(start_time, end_time, tg_full_name):
    print("time:", start_time, "-", end_time)
    res = CW.get_metric_statistics(
        StartTime=start_time,
        EndTime=end_time,
        Period=60,
        Statistics=["Sum"],
        **metric_spec(tg_full_name),
    )

    return res["Datapoints"]


def get_service_date():
    res = ECS.describe_services(cluster=CLUSTER, services=[SERVICE])
    return res["services"][0]["createdAt"]


def is_active(event):
    minutes = get_idle_minutes(event)
    now = datetime.now(timezone.utc)
    start_time = now - timedelta(minutes=minutes)

    print("service_date:", get_service_date())
    print("start_time:", start_time)

    if get_service_date() > start_time:
        print("Service is too new to shut down.")
        return True

    for tg_name in get_tg_full_names(event):
        print("tg_name:", tg_name)
        for dp in get_tg_metrics(start_time, now, tg_name):
            if dp["Sum"] > 0:
                return True
    return False


def set_desired_count(c):
    print("Setting desiredCount of service %s to %d" % (SERVICE, c))
    ECS.update_service(cluster=CLUSTER, service=SERVICE, desiredCount=c)


def get_rules(rule_arns):
    print("Fetching rules")
    return ELB.describe_rules(RuleArns=rule_arns)["Rules"]


def is_normal_condition(skipper_key, c):
    """Returns True if the condition is NOT the skipping condition"""
    q = c.get("QueryStringConfig")
    if not q:
        return True
    return q["Values"][0]["Key"] != skipper_key


def normalize_condition(c):
    """The DescribeRules API call returns conditions with both the Values and _Config which is invalid for modify_rule."""
    config_keys = [k for k in c if k.endswith("Config")]
    if len(config_keys) > 0 and "Values" in c:
        del c["Values"]
    return c


def enable_rules(skipper_key, rule_arns):
    for rule in get_rules(rule_arns):
        rule_arn = rule["RuleArn"]
        conditions = [
            normalize_condition(c)
            for c in rule["Conditions"]
            if is_normal_condition(skipper_key, c)
        ]
        print(f"Un-skipping {rule_arn}: {conditions}")
        ELB.modify_rule(
            RuleArn=rule_arn,
            Conditions=conditions,
        )


def disable_schedule_rule(rule_name):
    print("Disabling stopper schedule rule:", rule_name)
    EB.disable_rule(Name=rule_name)


def lambda_handler(event, context):
    print("event:", event)

    if is_stack_updating():
        print("Stack is not in a COMPLETE state. Will not shut down.")
        return

    if is_active(event):
        print("Service is active. Will not shut down.")
        return

    print("Service is inactive.")
    rule_arns = event["rule_arns"]
    schedule_rule_name = get_schedule_rule_name()
    skipper_key = get_rule_skipper_key(event)

    enable_rules(skipper_key, rule_arns)
    set_desired_count(0)
    disable_schedule_rule(schedule_rule_name)


if __name__ == "__main__":
    event = {
        "idle_minutes": 15,
        "target_group_names": ["targetgroup/x-Ecs-Targe-4HFPSCSW1BQW/73aa4b45250d7b79"],
        "rule_param_name": "CFN-AutoStopRuleParam-0oF3xIT923dy",
        "rule_arns": [
            "arn:aws:elasticloadbalancing:us-east-1:803071473383:listener-rule/app/sig-ban-alb/5597061b6c745440/893db79165865ecb/2fe13434d34b1ab4"
        ],
        "waiter_tg_arn": "arn:aws:elasticloadbalancing:us-east-1:803071473383:targetgroup/x-Ecs-AutoS-K6LUYPO403ON/a400f886418961ef",
    }
    lambda_handler(event, None)
