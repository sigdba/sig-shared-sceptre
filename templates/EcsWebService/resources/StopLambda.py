import os
import json
from datetime import datetime, timedelta, timezone

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
    return event["idle_minutes"]


def get_tg_full_names(event):
    return event["target_group_names"]


def get_waiter_tg_arn(event):
    return event["waiter_tg_arn"]


def get_rule_param_name(event):
    return event["rule_param_name"]


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


def stash_rule_actions(event, rule_arns):
    param_name = get_rule_param_name(event)

    # To avoid putting the system into a weird state by, for instance, stashing
    # the waiter action instead of the correct actions, we make sure that the
    # parameter contains its initial value. This value is put in the parameter
    # at stack creation and after successful restart. If it's not there then
    # something weird's happening so we'll abort.
    print("Checking parameter value")
    if SSM.get_parameter(Name=param_name)["Parameter"]["Value"] != "NONE":
        raise ValueError(
            f"Parameter {param_name} does not have expected value of 'NONE'"
        )

    print("Stashing rule actions")
    rules = ELB.describe_rules(RuleArns=rule_arns)["Rules"]
    SSM.put_parameter(
        Name=param_name,
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
    if is_active(event):
        print("Service is active. Will not shut down.")
        return

    print("Service is inactive.")
    rule_arns = event["rule_arns"]
    stash_rule_actions(event, rule_arns)
    set_desired_count(0)
    set_rules_to_wait(event, rule_arns)


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
