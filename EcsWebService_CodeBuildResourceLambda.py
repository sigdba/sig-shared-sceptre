#!/usr/bin/env python3
import os
import time
import traceback
import boto3
import cfnresponse

from functools import partial
from datetime import datetime


REGION = '${AWS::Region}'

# Check if we're in a test environment, and if so set the region from the
# environment or use a default.
if 'AWS::Region' in REGION:
    REGION = os.environ.get('AWS_DEFAULT_REGION', 'us-east-1')
    print("Test environment detected, setting REGION to", REGION)
else:
    print("REGION:", REGION)


CB = boto3.client('codebuild', region_name=REGION)
ECR = boto3.client('ecr', region_name=REGION)


def get_image_tags(repository_name):
    for page in ECR.get_paginator('list_images').paginate(repositoryName=repository_name, filter={'tagStatus': 'TAGGED'}):
       for id in page['imageIds']:
           yield id['imageTag']


def describe_images(repo_name, tags):
    image_ids = [{'imageTag': t} for t in tags]
    for page in ECR.get_paginator('describe_images').paginate(repositoryName=repo_name, imageIds=image_ids):
        for d in page['imageDetails']:
            yield d


def get_build_status(build_id):
    print('Fetching build status')
    return CB.batch_get_builds(ids=[build_id])['builds'][0]['buildStatus']


def do_build(props, res_fn):
    res = CB.start_build(projectName=props['ProjectName'],
                         environmentVariablesOverride=props['EnvironmentVariablesOverride'])
    build_props = res['build']
    build_num = build_props['buildNumber']
    build_id = build_props['id']

    print("Build: {} ({})".format(build_id, build_num))

    while True:
        print('Waiting 30 seconds')
        time.sleep(30)
        status = get_build_status(build_id)
        print('Build status:', status)
        if status == 'SUCCEEDED':
            print("Build succeeded.")
            return build_num, build_id
        elif status == 'IN_PROGRESS':
            continue
        else:
            res_fn(cfnresponse.FAILED, {}, reason="Build finished with status '{}'".format(status))
            return None, None


def find_image(repo, build_time, build_num):
    image_tags = [t for t in get_image_tags(repo) if t == build_num or t.endswith('-' + build_num)]
    images = [d for d in describe_images(repo, image_tags) if d['imagePushedAt'].replace(tzinfo=None) > build_time]
    if len(images) == 1:
        image = images[0]
        print('Found image:', image)
        print('Fetching Image URI')
        image_tag = image['imageTags'][0]  # TODO: It might be better to select the LONGEST tag rather than the first
        image['imageUri'] = '{}:{}'.format(
            ECR.describe_repositories(repositoryNames=[repo])['repositories'][0]['repositoryUri'], image_tag)
        print('ImageURI:', image['imageUri'])
        return image
    else:
        res_fn(cfnresponse.FAILED, {}, reason='Build succeeded but found {} matching images in ECR repository'.format(len(images)))
        return None


def do_create_update(event, res_fn):
    props = event['ResourceProperties']

    build_time = datetime.utcnow()
    build_num, build_id = do_build(props, res_fn)

    if build_num is None:
        return

    build_num = str(build_num)
    res_data = {'BuildId': build_id, 'BuildNum': build_num}

    if 'RepositoryName' in props:
        image = find_image(props['RepositoryName'], build_time, build_num)
        if image is None:
            return
        res_data['ImageURI'] = image['imageUri']

    res_fn(cfnresponse.SUCCESS, res_data)


def print_response(responseStatus, responseData, physicalResourceId=None, noEcho=False, reason=None):
    print('-----------------------------------------------------------')
    print("responseStatus:", responseStatus, "\nresponseData:", responseData, "\nphysicalResourceId:", physicalResourceId,
          "\nreason:", reason)
    print('-----------------------------------------------------------')


def lambda_handler(event, context):
    print('event:', event)
    req_type = event['RequestType']

    if context is None:
        # We're in a test environment
        res_fn = print_response
    else:
        res_fn = partial(cfnresponse.send, event, context)

    try:
        if req_type in ['Create', 'Update']:
            return do_create_update(event, res_fn)
        elif req_type == 'Delete':
            res_fn(cfnresponse.SUCCESS, {})
        else:
            print('No handler for event type:', req_type, '\nReturning failure.')
            res_fn(cfnresponse.FAILED, {}, reason='No handler for event type "{}"'.format(req_type))
    except Exception as err:
       traceback.print_exc()
       res_fn(cfnresponse.FAILED, {}, reason=str(err))


if __name__ == '__main__':
    event = {
        "RequestType" : "Create",
        "RequestId" : "somerequest",
        "ResponseURL" : "pre-signed-url-for-create-response",
        "ResourceType" : "Custom::MyCustomResourceType",
        "LogicalResourceId" : "SomeLocalResourceId",
        "StackId" : "arn:aws:cloudformation:us-east-2:namespace:stack/stack-name/guid",
        "ResourceProperties" : {
            "ProjectName": "banner-app",
            "EnvironmentVariablesOverride": [
                {'name': 'APP_VER', 'value': '9.24.0.1-PPRD'},
                {'name': 'APP_NAME', 'value': 'StudentApi'},
            ],
            "RepositoryName" : "banner-app"
        }
    }
    lambda_handler(event, None)
