import hashlib

from troposphere import (
    Template,
    Ref,
    Sub,
    GetAtt,
    Parameter,
    FindInMap,
    Base64,
    Output,
    Export,
)
from troposphere.autoscaling import (
    AutoScalingGroup,
    NotificationConfigurations,
    MetricsCollection,
    LaunchConfiguration,
    LifecycleHook,
    Tags as ASTags,
)
from troposphere.awslambda import Permission, Function, Code
from troposphere.cloudformation import AWSCustomObject
from troposphere.ec2 import SecurityGroup, SecurityGroupRule
from troposphere.ecs import (
    Cluster,
    ClusterSetting,
    CapacityProvider,
    AutoScalingGroupProvider,
    ManagedScaling,
    ClusterCapacityProviderAssociations,
    CapacityProviderStrategy,
)
from troposphere.iam import Role, Policy, InstanceProfile
from troposphere.kms import Key, Alias
from troposphere.policies import UpdatePolicy, AutoScalingRollingUpdate
from troposphere.sns import Topic, Subscription, SubscriptionResource
from troposphere.s3 import Bucket, PublicAccessBlockConfiguration

from model import *
from util import *

REGION_MAP = "RegionMap"


def md5(s):
    return hashlib.md5(s.encode("utf-8")).hexdigest()


# aws ssm get-parameters --names /aws/service/ecs/optimized-ami/amazon-linux-2/recommended
def region_map():
    return {
        "us-east-1": {"AMIID": "ami-0f06fc190dd71269e"},
        "us-east-2": {"AMIID": "ami-0d9574c101c76fa20"},
        "us-west-2": {"AMIID": "ami-0a65620cb9b1fd77d"},
    }


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
                                "Action": ["ssm:GetParameters"],
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
                SecurityGroupRule(CidrIp=c, IpProtocol="-1") for c in ingress_cidrs
            ],
        )
    )


def auto_scaling_group(name, subnets, launch_conf, max_size, desired_size, sns_topic):
    return add_resource(
        AutoScalingGroup(
            "Asg" + name,
            VPCZoneIdentifier=subnets,
            LaunchConfigurationName=Ref(launch_conf),
            MinSize=0,
            MaxSize=max_size,
            DesiredCapacity=desired_size,
            MetricsCollection=[MetricsCollection(Granularity="1Minute")],
            NotificationConfigurations=[
                NotificationConfigurations(
                    TopicARN=Ref(sns_topic),
                    NotificationTypes=["autoscaling:EC2_INSTANCE_TERMINATE"],
                )
            ],
            Tags=ASTags(Name=Sub("ecs-node-${AWS::StackName}")),
            UpdatePolicy=UpdatePolicy(
                AutoScalingRollingUpdate=AutoScalingRollingUpdate(
                    MaxBatchSize=1,
                    MinInstancesInService=1,
                    MinSuccessfulInstancesPercent=100,
                    PauseTime="PT0M",
                )
            ),
        )
    )


def launch_config(name, sgs, inst_type, inst_prof, keyName):
    return add_resource(
        LaunchConfiguration(
            "LaunchConf" + name,
            ImageId=FindInMap(REGION_MAP, Ref("AWS::Region"), "AMIID"),
            SecurityGroups=sgs,
            InstanceType=inst_type,
            IamInstanceProfile=Ref(inst_prof),
            KeyName=keyName,
            UserData=Base64(Sub(read_resource("UserData.txt"))),
        )
    )


def ecs_cluster(container_insights_enabled):
    return add_resource(
        Cluster(
            "EcsCluster",
            ClusterName=Ref("EnvName"),
            ClusterSettings=[
                ClusterSetting(
                    Name="containerInsights",
                    Value="enabled" if container_insights_enabled else "disabled",
                )
            ],
        )
    )


def asg_sns_topic(lambda_fn):
    return add_resource(
        Topic(
            "ASGSNSTopic",
            Subscription=[
                Subscription(Endpoint=GetAtt(lambda_fn, "Arn"), Protocol="lambda")
            ],
            DependsOn=lambda_fn,
        )
    )


def sns_lambda_role():
    return add_resource(
        Role(
            "SNSLambdaRole",
            AssumeRolePolicyDocument={
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"Service": ["autoscaling.amazonaws.com"]},
                        "Action": ["sts:AssumeRole"],
                    }
                ],
            },
            ManagedPolicyArns=[
                "arn:aws:iam::aws:policy/service-role/AutoScalingNotificationAccessRole"
            ],
            Path="/",
        )
    )


def lambda_execution_role():
    return add_resource(
        Role(
            "LambdaExecutionRole",
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
        )
    )


def lambda_invoke_permission(lambda_fn, sns_topic):
    return add_resource(
        Permission(
            "LambdaInvokePermission",
            FunctionName=Ref(lambda_fn),
            Action="lambda:InvokeFunction",
            Principal="sns.amazonaws.com",
            SourceArn=Ref(sns_topic),
        )
    )


def lambda_subs_to_topic(lambda_fn, sns_topic):
    return add_resource(
        SubscriptionResource(
            "LambdaSubscriptionToSNSTopic",
            Endpoint=GetAtt(lambda_fn, "Arn"),
            Protocol="lambda",
            TopicArn=Ref(sns_topic),
        )
    )


def asg_terminate_hook(asg, sns_topic, sns_fn_role):
    return add_resource(
        LifecycleHook(
            asg.title + "ASGTerminateHook",
            AutoScalingGroupName=Ref(asg),
            DefaultResult="ABANDON",  # TODO: Maybe this should be TERMINATE?
            HeartbeatTimeout="1800",
            LifecycleTransition="autoscaling:EC2_INSTANCE_TERMINATING",
            NotificationTargetARN=Ref(sns_topic),
            RoleARN=GetAtt(sns_fn_role, "Arn"),
            DependsOn=sns_topic,
        )
    )


def lambda_fn_for_asg(fn_ex_role):
    return add_resource(
        Function(
            "LambdaFunctionForASG",
            Description="Gracefully drain ECS tasks from EC2 instances before the instances are terminated by autoscaling.",
            Handler="index.lambda_handler",
            Role=GetAtt(fn_ex_role, "Arn"),
            Runtime="python3.6",
            MemorySize=128,
            Timeout=60,
            Code=Code(ZipFile=Sub(read_resource("TerminationLambda.py"))),
        )
    )


def lambda_fn_for_cps():
    return add_resource(
        Function(
            "LambdaFunctionForCpsReset",
            Description="Updates services in the cluster to use the new default CapacityProviderStrategy",
            Handler="index.lambda_handler",
            Role=GetAtt("LambdaExecutionRole", "Arn"),
            Runtime="python3.6",
            MemorySize=128,
            Timeout=60,
            Code=Code(ZipFile=Sub(read_resource("ResetCapacityProvidersLambda.py"))),
        )
    )


class CpsReset(AWSCustomObject):
    resource_type = "Custom::CpsReset"
    props = {"ServiceToken": (str, True), "StrategyHash": (str, True)}


def cps_reset_resource(scaling_group_props):
    return add_resource(
        CpsReset(
            "CpsReset",
            ServiceToken=GetAtt("LambdaFunctionForCpsReset", "Arn"),
            StrategyHash=md5(str(scaling_group_props)),
            DependsOn="CapacityProviderAssoc",
        )
    )


# TODO: Rewrite this
def capacity_provider(asg_props):
    asg = asg_props["asg"]
    return {
        **asg_props,
        "capacity_provider": add_resource(
            CapacityProvider(
                asg.title + "CapacityProvider",
                AutoScalingGroupProvider=AutoScalingGroupProvider(
                    AutoScalingGroupArn=Ref(asg),
                    ManagedTerminationProtection="DISABLED",  # For now, this is handled by our lifecycle Lambda
                    ManagedScaling=ManagedScaling(Status="ENABLED", TargetCapacity=100),
                ),
            )
        ),
    }


def capacity_provider_assoc(asg_props):
    return add_resource(
        ClusterCapacityProviderAssociations(
            "CapacityProviderAssoc",
            Cluster=Ref("EcsCluster"),
            CapacityProviders=[Ref(p["capacity_provider"]) for p in asg_props],
            DefaultCapacityProviderStrategy=[
                CapacityProviderStrategy(
                    CapacityProvider=Ref(p["capacity_provider"]),
                    Weight=p.get("weight", 1),
                )
                for p in asg_props
                if p.get("in_default_cps", True)
            ],
        )
    )


# TODO: Rewrite this
def scaling_groups(
    scaling_group_data,
    security_groups,
    node_profile,
    subnets,
    sns_topic,
    sns_fn_role,
):
    for asg_props in scaling_group_data:
        name = asg_props["name"]
        c = launch_config(
            name,
            security_groups,
            asg_props["node_type"],
            node_profile,
            asg_props["key_name"],
        )
        asg = auto_scaling_group(
            name,
            subnets,
            c,
            asg_props["max_size"],
            asg_props["desired_size"],
            sns_topic,
        )
        asg_terminate_hook(asg, sns_topic, sns_fn_role)
        yield {**asg_props, "asg": asg}


def sceptre_handler(sceptre_user_data):
    user_data = UserDataModel(**sceptre_user_data)

    add_param("VpcId", Type="String", Description="VPC to launch cluster in")
    add_param("EnvName", Type="String", Description="The name of the environment")

    TEMPLATE.add_mapping(REGION_MAP, region_map())

    node_role = node_instance_role()
    node_profile = node_instance_profile(node_role)
    fn_ex_role = lambda_execution_role()
    asg_lambda = lambda_fn_for_asg(fn_ex_role)
    sns_topic = asg_sns_topic(asg_lambda)
    sns_fn_role = sns_lambda_role()
    node_sg = node_security_group(user_data.ingress_cidrs)
    cluster = ecs_cluster(user_data.container_insights_enabled)

    service_role()
    lambda_invoke_permission(asg_lambda, sns_topic)
    lambda_subs_to_topic(asg_lambda, sns_topic)
    cluster_bucket()

    TEMPLATE.add_output(
        Output(
            "ClusterArnOutput",
            Value=Ref(cluster),
            Export=Export(Sub("${EnvName}-EcsEnv-EcsCluster")),
        )
    )

    TEMPLATE.add_output(
        Output(
            "ClusterBucketOutput",
            Value=Ref("ClusterBucket"),
            Export=Export(Sub("${EnvName}-EcsEnv-ClusterBucket")),
        )
    )

    # TODO: Rewrite this
    scaling_group_props = [g.dict() for g in user_data.scaling_groups]
    asgs = list(
        scaling_groups(
            scaling_group_props,
            [Ref(node_sg)] + user_data.node_security_groups,
            node_profile,
            user_data.subnet_ids,
            sns_topic,
            sns_fn_role,
        )
    )

    if user_data.auto_scaling_enabled:
        capacity_provider_assoc([capacity_provider(p) for p in asgs])
        if user_data.force_default_cps:
            lambda_fn_for_cps()
            cps_reset_resource(scaling_group_props)

    return TEMPLATE.to_json()
