import os
import urllib
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
CFN = boto3.client("cloudformation", region_name=REGION)
SFN = boto3.client("stepfunctions", region_name=REGION)


class Status(Enum):
    INITIAL = (0, "Service startup requested")
    STARTING = (1, "Service starting")
    LB_INITIAL = (2, "Checking service health")
    READY = (3, "Service ready")

    def __init__(self, order, label):
        self.order = order
        self.label = label


@lru_cache
def get_starter_arn():
    outputs = CFN.describe_stacks(StackName=STACK_ID)["Stacks"][0]["Outputs"]
    return [
        o["OutputValue"] for o in outputs if o["OutputKey"] == "StarterStateMachineArn"
    ][0]


def get_cluster_arn():
    return env("CLUSTER_ARN")


def get_service_arn():
    return env("SERVICE_ARN")


def get_refresh_seconds():
    return int(env("REFRESH_SECONDS", 10))


def get_user_css():
    return env("USER_CSS", "")


def get_title():
    return env("PAGE_TITLE", "${AWS::StackName}")


def get_heading():
    return env("HEADING", "Please wait while the service starts...")


def get_explanation():
    return env(
        "EXPLANATION",
        """This service has been shut down due to inactivity. It is now being
           restarted and will be available again shortly.""",
    )


def starter_is_running():
    return (
        len(
            SFN.list_executions(
                stateMachineArn=get_starter_arn(), statusFilter="RUNNING"
            )["executions"]
        )
        > 0
    )


def get_tg_arns():
    return {
        lb["targetGroupArn"]
        for lb in ECS.describe_services(
            cluster=get_cluster_arn(), services=[get_service_arn()]
        )["services"][0]["loadBalancers"]
    }


def get_tg_healths():
    return [
        [
            h["TargetHealth"]["State"]
            for h in ELB.describe_target_health(TargetGroupArn=tg_arn)[
                "TargetHealthDescriptions"
            ]
        ]
        for tg_arn in get_tg_arns()
    ]


def all_tgs_have_targets(tg_healths):
    for statuses in tg_healths:
        if len(statuses) < 1:
            return False
    return True


def all_tgs_have_healthy(tg_healths):
    for statuses in tg_healths:
        if "healthy" not in statuses:
            return False
    return True


def start_service():
    SFN.start_execution(stateMachineArn=get_starter_arn())


def get_service_status():
    if not starter_is_running():
        start_service()
        return Status.INITIAL

    tg_healths = get_tg_healths()
    # if all_tgs_have_healthy(tg_healths):
    #     return Status.READY
    if all_tgs_have_targets(tg_healths):
        return Status.LB_INITIAL

    return Status.READY


def get_url(event):
    proto = event.get("headers", {}).get("x-forwarded-proto", "https")
    path = event.get("path", "/")
    query = urllib.parse.urlencode(event.get("queryStringParameters", {}))
    return urllib.parse.urlunsplit((proto, event["headers"]["host"], path, query, ""))


def refresher_body(event, status):
    progress_pct = 100 / (len(Status.__members__) + 1) * (status.order + 1)
    # refresher_seconds = 1 if status == Status.READY else get_refresh_seconds()
    refresh_seconds = get_refresh_seconds()
    return f"""
    <html>
    <head>
        <title>{get_title()}</title>
        <style>
            body {{
               font-family: 'Lucida Grande', 'Helvetica Neue', Helvetica, Arial, sans-serif;
            }}

            .external {{
                display: table;
                position: absolute;
                top: 0;
                left: 0;
                height: 100%;
                width: 100%;
            }}

            .middle {{
                display: table-cell;
                vertical-align: middle;
            }}

            .internal {{
                margin-left: auto;
                margin-right: auto;
                width: 80%;
            }}

            #progress {{
                border: 1px solid black;
                width: 100%;
                margin: auto;
            }}

            #progress_fill {{
                background-color: blue;
                height: 2em;
            }}

            #status {{
                margin: auto;
                text-align: center;
                padding: 3px;
            }}
        </style>
        <style>
        {get_user_css()}
        </style>
        <meta http-equiv="refresh" content="{refresh_seconds}; url={get_url(event)}">
    </head>
    <body>
        <div class="external">
            <div class="middle">
                <div class="internal">
                    <h1>{get_heading()}</h1>
                    <p id="explanation">{get_explanation()} </p>
                    <div id="progress">
                        <div id="progress_fill" style="width: {progress_pct}%">&nbsp;</div>
                    </div>
                    <div id="status">{status.label}</div>
                </div>
            </div>
        </div>
    </body>
    </html>
    """


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
        "body": refresher_body(event, status),
    }


if __name__ == "__main__":
    import yaml

    event = {"httpMethod": "GET"}
    print(yaml.dump(lambda_handler(event, None)))
