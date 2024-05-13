import hashlib

from troposphere import Base64, GetAtt, Ref, Sub, Tags
from troposphere.autoscaling import (
    AutoScalingGroup,
    LaunchConfiguration,
    LifecycleHook,
    MetricsCollection,
    NotificationConfigurations,
)
from troposphere.autoscaling import Tags as ASTags
from troposphere.awslambda import Code, Function, Permission
from troposphere.cloudformation import AWSCustomObject
from troposphere.ec2 import SecurityGroup, SecurityGroupRule
from troposphere.ecs import (
    AutoScalingGroupProvider,
    CapacityProvider,
    CapacityProviderStrategy,
    Cluster,
    ClusterCapacityProviderAssociations,
    ClusterSetting,
    ManagedScaling,
)
from troposphere.iam import InstanceProfile, Policy, Role
from troposphere.policies import AutoScalingRollingUpdate, UpdatePolicy
from troposphere.s3 import Bucket, PublicAccessBlockConfiguration
from troposphere.sns import Subscription, SubscriptionResource, Topic

import model
from util import (
    TEMPLATE,
    add_export,
    add_param,
    add_resource,
    add_resource_once,
    read_resource,
    opts_with,
)


def md5(s):
    return hashlib.md5(s.encode("utf-8")).hexdigest()


def cluster_bucket():
    return add_resource(
        Bucket(
            "ClusterBucket",
            PublicAccessBlockConfiguration=PublicAccessBlockConfiguration(
                BlockPublicAcls=True,
                BlockPublicPolicy=True,
                IgnorePublicAcls=True,
                RestrictPublicBuckets=True,
            ),
        )
    )


def service_role():
    return add_resource(
        Role(
            "ServiceRole",
            AssumeRolePolicyDocument={
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"Service": ["ecs.amazonaws.com"]},
                        "Action": ["sts:AssumeRole"],
                    }
                ],
            },
            ManagedPolicyArns=[
                "arn:aws:iam::aws:policy/service-role/AmazonEC2ContainerServiceRole"
            ],
        )
    )


def node_instance_role():
    return add_resource(
        Role(
            "NodeInstanceRole",
            AssumeRolePolicyDocument={
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"Service": ["ec2.amazonaws.com"]},
                        "Action": ["sts:AssumeRole"],
                    }
                ],
            },
            ManagedPolicyArns=[
                "arn:aws:iam::aws:policy/service-role/AmazonEC2ContainerServiceforEC2Role",
                "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore",
                "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy",
            ],
            Policies=[
                Policy(
                    PolicyName="root",
                    PolicyDocument={
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Effect": "Allow",
                                "Action": [
                                    "ssm:GetParameters",
                                    "elasticfilesystem:DescribeMountTargets",
                                    "elasticfilesystem:DescribeAccessPoints",
                                    "elasticfilesystem:DescribeFileSystems",
                                    "ec2:DescribeAvailabilityZones",
                                ],
                                # TODO: We're having trouble with the consistency of these wildcards. For now we'll just let
                                #       it read any parameter. Perhaps we can control it by controlling access to the
                                #       decryption key instead.
                                # Resource: [ !Sub "arn:aws:ssm:::parameter/EcsEnv.${EnvName}.*" ]
                                "Resource": ["*"],
                            },
                            {
                                "Effect": "Allow",
                                "Action": [
                                    "logs:CreateLogGroup",
                                    "logs:CreateLogStream",
                                    "logs:PutLogEvents",
                                    "logs:DescribeLogStreams",
                                ],
                                "Resource": ["arn:aws:logs:*:*:*"],
                            },
                            {
                                "Effect": "Allow",
                                "Action": [
                                    "s3:ListBucket",
                                    "s3:GetObjectVersion",
                                    "s3:GetObjectVersionAcl",
                                    "s3:GetObject",
                                    "s3:GetObjectVersion",
                                ],
                                "Resource": [
                                    GetAtt("ClusterBucket", "Arn"),
                                    Sub("${ClusterBucket.Arn}/*"),
                                ],
                            },
                        ],
                    },
                )
            ],
        )
    )


def node_instance_profile(role):
    return add_resource(InstanceProfile("NodeInstanceProfile", Roles=[Ref(role)]))


def node_security_group(ingress_cidrs):
    return add_resource(
        SecurityGroup(
            "NodeSecurityGroup",
            GroupDescription="Security group for ECS nodes",
            VpcId=Ref("VpcId"),
            SecurityGroupEgress=[
                SecurityGroupRule(CidrIp="0.0.0.0/0", IpProtocol="-1")
            ],
            SecurityGroupIngress=[
                SecurityGroupRule(
                    CidrIp=c.cidr,
                    IpProtocol="-1",
                    **opts_with(Description=c.description)
                )
                for c in ingress_cidrs
            ],
        )
    )


def auto_scaling_group(
    name, subnets, launch_conf, max_size, max_lifetime_days, desired_size, tags
):
    return add_resource(
        AutoScalingGroup(
            "Asg" + name,
            VPCZoneIdentifier=subnets,
            LaunchConfigurationName=Ref(launch_conf),
            MinSize=0,
            MaxSize=max_size,
            DesiredCapacity=str(desired_size),
            MetricsCollection=[MetricsCollection(Granularity="1Minute")],
            Tags=ASTags(Name=Sub("ecs-node-${AWS::StackName}"), **tags),
            UpdatePolicy=UpdatePolicy(
                AutoScalingRollingUpdate=AutoScalingRollingUpdate(
                    MaxBatchSize=1,
                    MinInstancesInService=1,
                    MinSuccessfulInstancesPercent=100,
                    PauseTime="PT0M",
                )
            ),
            **opts_with(
                MaxInstanceLifetime=(max_lifetime_days, lambda secs: secs * 86400)
            )
        )
    )


def launch_config(name, sgs, inst_type, inst_prof, keyName, extra_node_user_data):
    return add_resource(
        LaunchConfiguration(
            "LaunchConf" + name,
            ImageId=Ref("AmiId"),
            SecurityGroups=sgs,
            InstanceType=inst_type,
            IamInstanceProfile=Ref(inst_prof),
            KeyName=keyName,
            UserData=Base64(
                Sub(read_resource("UserData.txt"), ExtraUserData=extra_node_user_data)
            ),
        )
    )


def ecs_cluster(user_data):
    return add_resource(
        Cluster(
            "EcsCluster",
            ClusterName=Ref("EnvName"),
            ClusterSettings=[
                ClusterSetting(
                    Name="containerInsights",
                    Value="enabled"
                    if user_data.container_insights_enabled
                    else "disabled",
                )
            ],
            Tags=Tags(**{**user_data.tags, **user_data.cluster_tags}),
        )
    )


def lambda_execution_role():
    return add_resource_once(
        "LambdaExecutionRole",
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
                                    "autoscaling:CompleteLifecycleAction",
                                    "logs:CreateLogGroup",
                                    "logs:CreateLogStream",
                                    "logs:PutLogEvents",
                                    "ecs:ListContainerInstances",
                                    "ecs:ListServices",
                                    "ecs:DescribeClusters",
                                    "ecs:DescribeServices",
                                    "ecs:DescribeContainerInstances",
                                    "ecs:UpdateContainerInstancesState",
                                    "ecs:UpdateService",
                                    "sns:Publish",
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
            ManagedPolicyArns=[
                "arn:aws:iam::aws:policy/service-role/AutoScalingNotificationAccessRole"
            ],
            Path="/",
        ),
    )


def lambda_fn_for_cps():
    return add_resource(
        Function(
            "LambdaFunctionForCpsReset",
            Description="Updates services in the cluster to use the new default CapacityProviderStrategy",
            Handler="index.lambda_handler",
            Role=lambda_execution_role().GetAtt("Arn"),
            Runtime="python3.9",
            MemorySize=128,
            Timeout=60,
            Code=Code(ZipFile=Sub(read_resource("ResetCapacityProvidersLambda.py"))),
        )
    )


class CpsReset(AWSCustomObject):
    resource_type = "Custom::CpsReset"
    props = {"ServiceToken": (str, True), "StrategyHash": (str, True)}


def cps_reset_resource(user_data):
    return add_resource(
        CpsReset(
            "CpsReset",
            ServiceToken=GetAtt("LambdaFunctionForCpsReset", "Arn"),
            StrategyHash=md5(str(user_data.scaling_groups)),
            DependsOn="CapacityProviderAssoc",
        )
    )


def capacity_provider(asg):
    return add_resource(
        CapacityProvider(
            asg.title + "CapacityProvider",
            AutoScalingGroupProvider=AutoScalingGroupProvider(
                AutoScalingGroupArn=Ref(asg),
                ManagedDraining="ENABLED",
                ManagedTerminationProtection="DISABLED",
                ManagedScaling=ManagedScaling(Status="ENABLED", TargetCapacity=100),
            ),
        )
    )


def capacity_provider_assoc(asgs_with_models):
    cps_with_models = [(capacity_provider(a), m) for a, m in asgs_with_models]
    return add_resource(
        ClusterCapacityProviderAssociations(
            "CapacityProviderAssoc",
            Cluster=Ref("EcsCluster"),
            CapacityProviders=[Ref(cp) for cp, _ in cps_with_models],
            DefaultCapacityProviderStrategy=[
                CapacityProviderStrategy(
                    CapacityProvider=Ref(cp),
                    Weight=sg_model.weight,
                )
                for cp, sg_model in cps_with_models
                if sg_model.in_default_cps
            ],
        )
    )


def scaling_group_with_resources(
    security_groups, node_profile, subnets, tags, sg_model
):
    lc = launch_config(
        sg_model.name,
        security_groups,
        sg_model.node_type,
        node_profile,
        sg_model.key_name,
        sg_model.extra_node_user_data,
    )
    asg = auto_scaling_group(
        sg_model.name,
        subnets,
        lc,
        sg_model.max_size,
        sg_model.max_instance_lifetime_days,
        sg_model.desired_size,
        tags,
    )
    # lifecycle.asg_terminate_hook(asg)
    return asg


def sceptre_handler(sceptre_user_data):
    add_param(
        "VpcId",
        Type="String",
        Description="The ID of the VPC where the ECS cluster will be created.",
    )
    add_param("EnvName", Type="String", Description="The name of the ECS cluster.")
    add_param(
        "AmiId",
        Description="AMI ID for EC2 cluster nodes",
        Type="AWS::SSM::Parameter::Value<AWS::EC2::Image::Id>",
        Default="/aws/service/ecs/optimized-ami/amazon-linux-2/recommended/image_id",
        # Default="/aws/service/ecs/optimized-ami/amazon-linux-2023/recommended/image_id",
    )
    if sceptre_user_data is None:
        # We're generating documetation. Return the template with just parameters.
        return TEMPLATE

    user_data = model.UserDataModel(**sceptre_user_data)

    # fn_ex_role = lambda_execution_role()
    cluster = ecs_cluster(user_data)

    service_role()
    cluster_bucket()

    add_export("ClusterArnOutput", Sub("${EnvName}-EcsEnv-EcsCluster"), Ref(cluster))
    add_export(
        "ClusterBucketOutput",
        Sub("${EnvName}-EcsEnv-ClusterBucket"),
        Ref("ClusterBucket"),
    )

    if len(user_data.scaling_groups) > 0:
        node_sg = node_security_group(user_data.ingress_cidrs)
        node_role = node_instance_role()
        node_profile = node_instance_profile(node_role)
        all_security_groups = [Ref(node_sg)] + user_data.node_security_groups

        # Lifecycle
        # lifecycle.init()

        asgs_with_models = [
            (
                scaling_group_with_resources(
                    all_security_groups,
                    node_profile,
                    user_data.subnet_ids,
                    {**user_data.tags, **user_data.asg_tags, **g.tags},
                    g,
                ),
                g,
            )
            for g in user_data.scaling_groups
        ]

        if user_data.auto_scaling_enabled:
            capacity_provider_assoc(asgs_with_models)
            if user_data.force_default_cps:
                lambda_fn_for_cps()
                cps_reset_resource(user_data)

        add_export(
            "NodeSecurityGroupOutput", Sub("${EnvName}-EcsEnv-NodeSg"), Ref(node_sg)
        )

    return TEMPLATE.to_json()
