from troposphere import GetAtt, Sub, Tags
from troposphere.iam import Policy, Role
from troposphere.cloudformation import AWSCustomObject
from troposphere.awslambda import Permission, Function, Code
from util import *


def lambda_execution_role():
    return add_resource_once(
        "LambdaExecutionRoleForRootVolProps",
        lambda name: Role(
            name,
            Policies=[
                Policy(
                    PolicyName="lambda-inline",
                    PolicyDocument={
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Effect": "Allow",
                                "Action": [
                                    "logs:CreateLogGroup",
                                    "logs:CreateLogStream",
                                    "logs:PutLogEvents",
                                    "ec2:DescribeInstances",
                                    "ec2:ModifyVolume",
                                    "ec2:CreateTags",
                                    "ec2:DescribeVolumes",
                                ],
                                "Resource": "*",
                            }
                        ],
                    },
                )
            ],
            AssumeRolePolicyDocument={
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"Service": ["lambda.amazonaws.com"]},
                        "Action": ["sts:AssumeRole"],
                    }
                ],
            },
            Path="/",
        ),
    )


def lambda_fn_for_root_vol_props():
    return add_resource_once(
        "LambdaFunctionForRootVolProps",
        lambda title: Function(
            title,
            Description="Retrieves information on an EC2 instance's root volume and optionally sets tags and size",
            Handler="index.lambda_handler",
            Role=GetAtt(lambda_execution_role(), "Arn"),
            Runtime="python3.9",
            MemorySize=128,
            Timeout=900,
            Code=Code(ZipFile=Sub(read_resource("ec2-root-ebs-properties.py"))),
        ),
    )


class RootVolProps(AWSCustomObject):
    resource_type = "Custom::RootVolProps"
    props = {
        "ServiceToken": (str, True),
        "InstanceId": (str, True),
        "Tags": (list, False),
        "Size": (int, False),
    }


def root_vol_props(ec2_inst, user_data):
    tags = {"Name": f"{user_data.instance_name}: /", **user_data.root_volume_tags}
    return add_resource(
        RootVolProps(
            "RootVolProps",
            ServiceToken=GetAtt(lambda_fn_for_root_vol_props(), "Arn"),
            InstanceId=Ref(ec2_inst),
            Tags=Tags(tags),
            **opts_with(Size=user_data.root_volume_size),
        )
    )
