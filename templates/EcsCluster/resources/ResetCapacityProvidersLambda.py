import boto3
import cfnresponse
import os
from functools import partial
import traceback

CLUSTER = "${EnvName}"
REGION = "${AWS::Region}"

# Check if we're in a test environment, and if so set the region from the
# environment or use a default.
if "AWS::Region" in REGION:
    REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
    print("Test environment detected, setting REGION to", REGION)
else:
    print("REGION:", REGION)


ECS = boto3.client("ecs", region_name=REGION)


def chunks(it, chunk_size):
    lst = list(it)
    return [lst[i : i + chunk_size] for i in range(0, len(lst), chunk_size)]


def get_default_cps():
    return ECS.describe_clusters(clusters=[CLUSTER])["clusters"][0][
        "defaultCapacityProviderStrategy"
    ]


def get_service_arns():
    paginator = ECS.get_paginator("list_services")
    for page in paginator.paginate(cluster=CLUSTER, launchType="EC2"):
        for arn in page["serviceArns"]:
            yield arn


def get_services():
    for chunk in chunks(get_service_arns(), 10):
        res = ECS.describe_services(cluster=CLUSTER, services=chunk)
        for svc in res["services"]:
            yield svc


def set_cps(service_arn, cps):
    try:
        ECS.update_service(
            cluster=CLUSTER,
            service=service_arn,
            capacityProviderStrategy=cps,
            forceNewDeployment=True,
        )
    except:
        print("Error updating CPS for service", service_arn)
        print("-----------------------------------------------------------")
        traceback.print_exc()
        print("-----------------------------------------------------------")


def update_all_services():
    new_cps = get_default_cps()
    print("Updating all services to new capacityProviderStrategy:", new_cps)
    for service in get_services():
        service_name = service["serviceName"]
        old_cps = service.get("capacityProviderStrategy", [])
        sched_strat = service["schedulingStrategy"]
        if old_cps == new_cps:
            print(service_name, "already has the correct capacityProviderStrategy")
        elif sched_strat != "REPLICA":
            print(service_name, "scheduling strategy is", sched_strat, "not REPLICA")
        else:
            print(
                f"Switching {service_name} capacityProviderStrategy from {old_cps} to {new_cps}"
            )
            set_cps(service["serviceArn"], new_cps)


def print_response(
    responseStatus, responseData, physicalResourceId=None, noEcho=False, reason=None
):
    print("-----------------------------------------------------------")
    print(
        f"responseStatus: {responseStatus}",
        f"\nresponseData: {responseData}",
        f"\nphysicalResourceId: {physicalResourceId}",
        f"\nreason: {reason}",
    )
    print("-----------------------------------------------------------")


def lambda_handler(event, context):
    print("event:", event)
    rt = event["RequestType"]

    if context is None:
        # We're in a test environment
        res_fn = print_response
    else:
        res_fn = partial(cfnresponse.send, event, context)

    try:
        if rt in ["Create", "Update"]:
            update_all_services()
        res_fn(cfnresponse.SUCCESS, {})
    except Exception as err:
        traceback.print_exc()
        res_fn(cfnresponse.FAILED, {}, reason=str(err))
