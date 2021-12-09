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


def node_instance_profile():
    return add_resource(
        InstanceProfile("NodeInstanceProfile", Roles=[Ref(node_instance_role())])
    )


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


def lambda_fn_for_asg():
    return add_resource(
        Function(
            "LambdaFunctionForASG",
            Description="Gracefully drain ECS tasks from EC2 instances before the instances are terminated by autoscaling.",
            Handler="index.lambda_handler",
            Role=GetAtt(lambda_execution_role(), "Arn"),
            Runtime="python3.6",
            MemorySize=128,
            Timeout=60,
            Code=Code(ZipFile=Sub(read_resource("TerminationLambda.py"))),
        )
    )


def lambda_invoke_permission(fn, source):
    return add_resource_once(
        "LambdaInvokePermission",
        lambda name: Permission(
            name,
            FunctionName=Ref(fn),
            Action="lambda:InvokeFunction",
            Principal="sns.amazonaws.com",
            SourceArn=Ref(source),
        ),
    )


def asg_sns_topic():
    lambda_fn = lambda_fn_for_asg()
    return add_resource(
        Topic(
            "ASGSNSTopic",
            Subscription=[
                Subscription(Endpoint=GetAtt(lambda_fn, "Arn"), Protocol="lambda")
            ],
            DependsOn=lambda_fn,
        )
    )


def launch_config(user_data, sg_model):
    return add_resource(
        LaunchConfiguration(
            "LaunchConf" + sg_model.name,
            ImageId=FindInMap(REGION_MAP, Ref("AWS::Region"), "AMIID"),
            SecurityGroups=user_data.node_security_groups,
            InstanceType=sg_model.node_type,
            IamInstanceProfile=Ref("NodeInstanceProfile"),
            KeyName=sg_model.key_name,
            UserData=Base64(Sub(read_resource("UserData.txt"))),
        )
    )


def lambda_subs_to_topic():
    return add_resource(
        SubscriptionResource(
            "LambdaSubscriptionToSNSTopic",
            Endpoint=GetAtt(lambda_fn_for_asg(), "Arn"),
            Protocol="lambda",
            TopicArn=Ref(asg_sns_topic()),
        )
    )


def sns_lambda_role():
    return add_resource_once(
        "SNSLambdaRole",
        lambda name: Role(
            name,
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
        ),
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


def cps_reset_resource(sg_model):
    return add_resource(
        CpsReset(
            "CpsReset",
            ServiceToken=GetAtt("LambdaFunctionForCpsReset", "Arn"),
            StrategyHash=md5(str(sg_model.dict())),
            DependsOn="CapacityProviderAssoc",
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
        )
    )


def asg_terminate_hook(asg):
    sns_topic = "ASGSNSTopic"
    return add_resource(
        LifecycleHook(
            asg.title + "ASGTerminateHook",
            AutoScalingGroupName=Ref(asg),
            DefaultResult="TERMINATE",
            HeartbeatTimeout="1800",
            LifecycleTransition="autoscaling:EC2_INSTANCE_TERMINATING",
            NotificationTargetARN=Ref(sns_topic),
            RoleARN=GetAtt(sns_lambda_role(), "Arn"),
            DependsOn=sns_topic,
        )
    )


def auto_scaling_group(user_data, sg_model):
    ret = add_resource(
        AutoScalingGroup(
            clean_title("Asg" + sg_model.name),
            VPCZoneIdentifier=user_data.subnets,
            LaunchConfigurationName=Ref(launch_config(user_data, sg_model)),
            MinSize=0,
            MaxSize=sg_model.max_size,
            DesiredCapacity=sg_model.desired_size,
            MetricsCollection=[MetricsCollection(Granularity="1Minute")],
            NotificationConfigurations=[
                NotificationConfigurations(
                    TopicARN=Ref(asg_sns_topic()),
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

    asg_terminate_hook(ret)
    return ret


def capacity_provider(sg_model, asg):
    return add_resource(
        CapacityProvider(
            clean_title(sg_model.name + "CapacityProvider"),
            AutoScalingGroupProvider=AutoScalingGroupProvider(
                AutoScalingGroupArn=Ref(asg),
                ManagedTerminationProtection="DISABLED",  # For now, this is handled by our lifecycle Lambda
                ManagedScaling=ManagedScaling(Status="ENABLED", TargetCapacity=100),
            ),
        )
    )


def capacity_provider_assoc(asg_props):
    return ClusterCapacityProviderAssociations(
        "CapacityProviderAssoc",
        Cluster=Ref("EcsCluster"),
        CapacityProviders=[Ref(p["capacity_provider"]) for p in asg_props],
        DefaultCapacityProviderStrategy=[
            CapacityProviderStrategy(
                CapacityProvider=Ref(p["capacity_provider"]), Weight=p.get("weight", 1)
            )
            for p in asg_props
            if p.get("in_default_cps", True)
        ],
    )


def sceptre_handler(sceptre_user_data):
    user_data = UserDataModel(**sceptre_user_data)

    add_param("VpcId", Type="String", Description="VPC to launch cluster in")
    add_param("EnvName", Type="String", Description="The name of the environment")

    TEMPLATE.add_mapping(REGION_MAP, region_map())

    # node_profile = r(node_instance_profile(node_role))
    # fn_ex_role = r(lambda_execution_role())
    # asg_lambda = r(lambda_fn_for_asg(fn_ex_role))
    # sns_topic = r(asg_sns_topic(asg_lambda))
    # sns_fn_role = r(sns_lambda_role())
    # node_sg = r(node_security_group(vpc_id, sceptre_user_data['ingress_cidrs']))
    ecs_cluster(user_data)

    # r(lambda_invoke_permission(asg_lambda, sns_topic))
    # r(lambda_subs_to_topic(asg_lambda, sns_topic))
    # r(cluster_bucket())

    # template.add_output(Output("ClusterArnOutput",
    #                            Value=Ref(cluster),
    #                            Export=Export(Sub("${EnvName}-EcsEnv-EcsCluster"))))

    # template.add_output(Output("ClusterBucketOutput",
    #                            Value=Ref('ClusterBucket'),
    #                            Export=Export(Sub("${EnvName}-EcsEnv-ClusterBucket"))))
    #

    asgs_with_models = [
        (auto_scaling_group(user_data, g), g) for g in user_data.scaling_groups
    ]

    # if sceptre_user_data.get('auto_scaling_enabled', False):
    #     r(capacity_provider_assoc([capacity_provider(r, p) for p in asgs]))
    #     if sceptre_user_data.get('force_default_cps', False):
    #         r(lambda_fn_for_cps())
    #         r(cps_reset_resource(scaling_group_props))

    return TEMPLATE.to_json()
