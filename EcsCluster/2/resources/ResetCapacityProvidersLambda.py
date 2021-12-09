import boto3
import cfnresponse

CLUSTER = '${EnvName}'
REGION = '${AWS::Region}'

ECS = boto3.client('ecs', region_name=REGION)


def chunks(it, chunk_size):
    lst = list(it)
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


def get_default_cps():
    return ECS.describe_clusters(clusters=[CLUSTER])['clusters'][0]['defaultCapacityProviderStrategy']


def get_service_arns():
    paginator = ECS.get_paginator('list_services')
    for page in paginator.paginate(cluster=CLUSTER, launchType='EC2'):
        for arn in page['serviceArns']:
            yield arn


def get_services():
    for chunk in chunks(get_service_arns(), 10):
        res = ECS.describe_services(cluster=CLUSTER, services=chunk)
        for svc in res['services']:
            yield svc


def set_cps(service_arn, cps):
    ECS.update_service(cluster=CLUSTER, service=service_arn, capacityProviderStrategy=cps, forceNewDeployment=True)


def update_all_services():
    new_cps = get_default_cps()
    print('Updating all services to new capacityProviderStrategy:', new_cps)
    for service in get_services():
        service_name = service['serviceName']
        old_cps = service.get('capacityProviderStrategy', [])
        if old_cps == new_cps:
            print(service_name, 'already has the correct capacityProviderStrategy')
        else:
            print('Switching', service_name, 'capacityProviderStrategy from', old_cps, 'to', new_cps)
            set_cps(service['serviceArn'], new_cps)


def lambda_handler(event, context):
    print('event:', event)
    rt = event['RequestType']
    if rt in ['Create', 'Update']:
        update_all_services()
    cfnresponse.send(event, context, cfnresponse.SUCCESS, {})
