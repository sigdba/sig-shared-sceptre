import boto3

CLUSTER = "${ClusterArn}"
REGION = "${AWS::Region}"
SERVICE = "${Service}"

ECS = boto3.client("ecs", region_name=REGION)


def set_desired_count(c):
    print("Setting desiredCount of service %s to %d" % (SERVICE, c))
    res = ECS.update_service(cluster=CLUSTER, service=SERVICE, desiredCount=c)
    print("Response:", res)


def lambda_handler(event, _):
    print("event:", event)
    set_desired_count(event["desired_count"])
