import os
import boto3
import time
import math
import traceback
import cfnresponse

from botocore.exceptions import ClientError
from functools import partial, reduce
from datetime import datetime

REGION = "${AWS::Region}"

# Check if we're in a test environment, and if so set the region from the
# environment or use a default.
if "AWS::Region" in REGION:
    REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
    print("Test environment detected, setting REGION to", REGION)
else:
    print("REGION:", REGION)


ec2 = boto3.client("ec2", region_name=REGION)
ec2_res = boto3.resource("ec2", region_name=REGION)


# This function returns a generator of "nap times" for retrying an operation. It will first perform an exponential
# backoff but as the Lambda timeout approaches will ramp up again in an attempt to finish before the timeout.
def retry_backoff(min_sec=1, max_sec=60, lifetime=900):
    deadline = time.time() + lifetime
    retries = 0
    while True:
        yield max(
            min_sec,
            min(max_sec, math.pow(2, retries) / 10, (deadline - time.time()) / 2.0),
        )
        retries = retries + 1


def get_root_ebs_vol_id(instance_id):
    print("Fetching root volume ID for instance:", instance_id)
    inst = ec2.describe_instances(InstanceIds=[instance_id])["Reservations"][0][
        "Instances"
    ][0]
    if inst["RootDeviceType"] != "ebs":
        raise ValueError(
            "Root device of instance %s is type '%s' but only EBS volumes can be modified by this module"
        )
    root_vol_name = inst["RootDeviceName"]
    return [
        m["Ebs"]["VolumeId"]
        for m in inst["BlockDeviceMappings"]
        if m["DeviceName"] == root_vol_name
    ][0]


def set_ebs_vol_tags(volume_id, tags):
    print("setting tags on volume", volume_id, ":", tags)
    res = ec2_res.Volume(volume_id).create_tags(Tags=tags)
    print("create_tags response:", res)


def set_ebs_vol_size(volume_id, size_gb):
    print("fetching current size of volume:", volume_id)
    vol = ec2_res.Volume(volume_id)
    cur_size = vol.size
    print(volume_id, "current size:", cur_size)
    if size_gb > cur_size:
        print("Current volume state:", vol.state)
        print("setting size on volume", volume_id, ":", size_gb)
        for nap_time in retry_backoff():
            try:
                res = ec2.modify_volume(VolumeId=volume_id, Size=size_gb)
                print("modify_volume response:", res)
                break
            except ClientError as err:
                if "Unavailable" in str(err):
                    print("ClientError: {0}".format(err))
                    print("Will retry in %0.2f seconds" % nap_time)
                    time.sleep(nap_time)
                else:
                    raise err
    else:
        print(
            volume_id,
            "current size greater than or equal to",
            size_gb,
            ". Skipping resize.",
        )


def do_create_update(event, res_fn):
    props = event["ResourceProperties"]
    inst_id = props["InstanceId"]
    vol_id = get_root_ebs_vol_id(inst_id)

    tags = props.get("Tags", None)
    size = props.get("Size", None)

    if tags is not None:
        set_ebs_vol_tags(vol_id, tags)
    if size is not None:
        set_ebs_vol_size(vol_id, int(size))

    ret = {"PhysicalResourceId": inst_id, "Data": {"RootEbsVolumeId": vol_id}}
    res_fn(cfnresponse.SUCCESS, ret)


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
    req_type = event["RequestType"]

    if context is None:
        # We're in a test environment
        res_fn = print_response
    else:
        res_fn = partial(cfnresponse.send, event, context)

    try:
        if req_type in ["Create", "Update"]:
            return do_create_update(event, res_fn)
        elif req_type == "Delete":
            res_fn(cfnresponse.SUCCESS, {})
        else:
            print("No handler for event type:", req_type, "\nReturning failure.")
            res_fn(
                cfnresponse.FAILED, {}, reason=f'No handler for event type "{req_type}"'
            )
    except Exception as err:
        traceback.print_exc()
        res_fn(cfnresponse.FAILED, {}, reason=str(err))


if __name__ == "__main__":
    event = {
        "RequestType": "Create",
        "RequestId": "somerequest",
        "ResponseURL": "pre-signed-url-for-create-response",
        "ResourceType": "Custom::MyCustomResourceType",
        "LogicalResourceId": "SomeLocalResourceId",
        "StackId": "arn:aws:cloudformation:us-east-2:namespace:stack/stack-name/guid",
        "ResourceProperties": {"InstanceId": "i-0f70737a54b26453f"},
    }
    lambda_handler(event, None)
