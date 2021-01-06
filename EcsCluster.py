import os
import os.path

from troposphere import Template, Ref, Sub, GetAtt, Parameter, FindInMap, Base64, Output, Export
from troposphere.autoscaling import AutoScalingGroup, NotificationConfigurations, MetricsCollection, \
    LaunchConfiguration, LifecycleHook, Tags as ASTags
from troposphere.awslambda import Permission, Function, Code
from troposphere.ec2 import SecurityGroup, SecurityGroupRule
from troposphere.ecs import Cluster, ClusterSetting
from troposphere.iam import Role, Policy, InstanceProfile
from troposphere.kms import Key, Alias
from troposphere.policies import UpdatePolicy, AutoScalingRollingUpdate
from troposphere.sns import Topic, Subscription, SubscriptionResource

REGION_MAP = "RegionMap"


def read_local_file(path):
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), path), 'r') as fp:
        return fp.read()


# aws ssm get-parameters --names /aws/service/ecs/optimized-ami/amazon-linux-2/recommended
def region_map():
    return {
        "us-east-1": {"AMIID": "ami-0f06fc190dd71269e"},
        "us-east-2": {"AMIID": "ami-0d9574c101c76fa20"},
        "us-west-2": {"AMIID": "ami-0a65620cb9b1fd77d"}
    }


def parameter_key(ssm_key_admins):
    return Key(
        "ParameterKey",
        Description="Key used to encrypt parameters in the SSM parameter store",
        EnableKeyRotation=False,
        KeyPolicy={
            "Version": "2012-10-17",
            "Statement": [{
                "Sid": "Allow administration of the key",
                "Effect": "Allow",
                "Principal": {
                    "AWS": [Sub(a) for a in ssm_key_admins]
                },
                "Action": [
                    "kms:Create*",
                    "kms:Describe*",
                    "kms:Enable*",
                    "kms:List*",
                    "kms:Put*",
                    "kms:Update*",
                    "kms:Revoke*",
                    "kms:Disable*",
                    "kms:Get*",
                    "kms:Delete*",
                    "kms:ScheduleKeyDeletion",
                    "kms:CancelKeyDeletion"
                ],
                "Resource": "*"
            }]
        }
    )


def parameter_key_alias(key):
    return Alias(
        "ParameterKeyAlias",
        AliasName=Sub("alias/${AWS::StackName}-ParameterKey"),
        TargetKeyId=Ref(key)
    )


def service_role():
    return Role(
        "ServiceRole",
        AssumeRolePolicyDocument={
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"Service": ["ecs.amazonaws.com"]},
                "Action": ['sts:AssumeRole']
            }]
        },
        ManagedPolicyArns=["arn:aws:iam::aws:policy/service-role/AmazonEC2ContainerServiceRole"]
    )


def node_instance_role(par_key):
    return Role(
        "NodeInstanceRole",
        AssumeRolePolicyDocument={
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"Service": ["ec2.amazonaws.com"]},
                "Action": ['sts:AssumeRole']
            }]
        },
        ManagedPolicyArns=["arn:aws:iam::aws:policy/service-role/AmazonEC2ContainerServiceforEC2Role"],
        Policies=[
            Policy(
                PolicyName="root",
                PolicyDocument={
                    "Version": '2012-10-17',
                    "Statement": [
                        {"Effect": "Allow",
                         "Action": ['kms:Decrypt'],
                         "Resource": [GetAtt(par_key, 'Arn')]},
                        {"Effect": "Allow",
                         "Action": ['ssm:GetParameters'],

                         # TODO: We're having trouble with the consistency of these wildcards. For now we'll just let
                         #       it read any parameter. Perhaps we can control it by controlling access to the
                         #       decryption key instead.
                         # Resource: [ !Sub "arn:aws:ssm:::parameter/EcsEnv.${EnvName}.*" ]
                         "Resource": ['*']},
                        {"Effect": "Allow",
                         "Action": ["logs:CreateLogGroup",
                                    "logs:CreateLogStream",
                                    "logs:PutLogEvents",
                                    "logs:DescribeLogStreams"],
                         "Resource": ['arn:aws:logs:*:*:*']}]
                }
            )
        ]
    )


def node_instance_profile(role):
    return InstanceProfile(
        "NodeInstanceProfile",
        Roles=[Ref(role)]
    )


def node_security_group(vpc_id, ingress_cidrs):
    return SecurityGroup(
        "NodeSecurityGroup",
        GroupDescription="Security group for ECS nodes",
        VpcId=Ref(vpc_id),
        SecurityGroupEgress=[SecurityGroupRule(CidrIp="0.0.0.0/0", IpProtocol="-1")],
        SecurityGroupIngress=[SecurityGroupRule(CidrIp=c, IpProtocol="-1") for c in ingress_cidrs]
    )


def auto_scaling_group(name, subnets, launch_conf, max_size, desired_size, sns_topic):
    return AutoScalingGroup(
        "Asg" + name,
        VPCZoneIdentifier=Ref(subnets),
        LaunchConfigurationName=Ref(launch_conf),
        MinSize=0,
        MaxSize=max_size,
        DesiredCapacity=desired_size,
        MetricsCollection=[MetricsCollection(Granularity="1Minute")],
        NotificationConfigurations=[
            NotificationConfigurations(
                TopicARN=Ref(sns_topic),
                NotificationTypes=["autoscaling:EC2_INSTANCE_TERMINATE"]
            )
        ],
        Tags=ASTags(Name=Sub("ecs-node-${AWS::StackName}")),

        UpdatePolicy=UpdatePolicy(
            AutoScalingRollingUpdate=AutoScalingRollingUpdate(
                MaxBatchSize=1,
                MinInstancesInService=1,
                MinSuccessfulInstancesPercent=100,
                PauseTime="PT0M"
            )
        )
    )


def launch_config(name, sgs, inst_type, inst_prof, keyName):
    return LaunchConfiguration(
        "LaunchConf" + name,
        ImageId=FindInMap(REGION_MAP, Ref('AWS::Region'), "AMIID"),
        SecurityGroups=sgs,
        InstanceType=inst_type,
        IamInstanceProfile=Ref(inst_prof),
        KeyName=keyName,
        UserData=Base64(Sub(read_local_file('EcsCluster_UserData.txt')))
    )


def ecs_cluster():
    return Cluster(
        "EcsCluster",
        ClusterName=Ref("EnvName"),
        ClusterSettings=[ClusterSetting(Name="containerInsights", Value="enabled")]
    )


def asg_sns_topic(lambda_fn):
    return Topic(
        "ASGSNSTopic",
        Subscription=[Subscription(Endpoint=GetAtt(lambda_fn, "Arn"), Protocol="lambda")],
        DependsOn=lambda_fn
    )


def sns_lambda_role():
    return Role(
        "SNSLambdaRole",
        AssumeRolePolicyDocument={
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"Service": ["autoscaling.amazonaws.com"]},
                "Action": ["sts:AssumeRole"]
            }]
        },
        ManagedPolicyArns=["arn:aws:iam::aws:policy/service-role/AutoScalingNotificationAccessRole"],
        Path="/"
    )


def lambda_execution_role():
    return Role(
        "LambdaExecutionRole",
        Policies=[Policy(
            PolicyName="lambda-inline",
            PolicyDocument={
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Action": [
                        "autoscaling:CompleteLifecycleAction",
                        "logs:CreateLogGroup",
                        "logs:CreateLogStream",
                        "logs:PutLogEvents",
                        "ecs:ListContainerInstances",
                        "ecs:DescribeContainerInstances",
                        "ecs:UpdateContainerInstancesState",
                        "sns:Publish"
                    ],
                    "Resource": "*"
                }]
            }
        )],
        AssumeRolePolicyDocument={
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"Service": ["lambda.amazonaws.com"]},
                "Action": ["sts:AssumeRole"]
            }]
        },
        ManagedPolicyArns=["arn:aws:iam::aws:policy/service-role/AutoScalingNotificationAccessRole"],
        Path="/"
    )


def lambda_invoke_permission(lambda_fn, sns_topic):
    return Permission(
        "LambdaInvokePermission",
        FunctionName=Ref(lambda_fn),
        Action="lambda:InvokeFunction",
        Principal="sns.amazonaws.com",
        SourceArn=Ref(sns_topic)
    )


def lambda_subs_to_topic(lambda_fn, sns_topic):
    return SubscriptionResource(
        "LambdaSubscriptionToSNSTopic",
        Endpoint=GetAtt(lambda_fn, "Arn"),
        Protocol="lambda",
        TopicArn=Ref(sns_topic)
    )


def asg_terminate_hook(asg, sns_topic, sns_fn_role):
    return LifecycleHook(
        asg.title + "ASGTerminateHook",
        AutoScalingGroupName=Ref(asg),
        DefaultResult="ABANDON",  # TODO: Maybe this should be TERMINATE?
        HeartbeatTimeout="1800",
        LifecycleTransition="autoscaling:EC2_INSTANCE_TERMINATING",
        NotificationTargetARN=Ref(sns_topic),
        RoleARN=GetAtt(sns_fn_role, "Arn"),
        DependsOn=sns_topic
    )


def lambda_fn_for_asg(fn_ex_role):
    return Function(
        "LambdaFunctionForASG",
        Description=
        "Gracefully drain ECS tasks from EC2 instances before the instances are terminated by autoscaling.",
        Handler="index.lambda_handler",
        Role=GetAtt(fn_ex_role, "Arn"),
        Runtime="python3.6",
        MemorySize=128,
        Timeout=60,
        Code=Code(ZipFile=Sub(read_local_file("EcsCluster_TerminationLambda.py")))
    )


def sceptre_handler(sceptre_user_data):
    template = Template()

    # Convenience function for adding parameters
    def p(*args, **kwargs):
        ret = Parameter(*args, **kwargs)
        template.add_parameter(ret)
        return ret

    # Convenience function for adding resources
    def r(ret):
        template.add_resource(ret)
        return ret

    #
    # Parameters
    #
    # TODO: Make parameter usage consistent using variables.
    vpc_id = p("VpcId", Type="String", Description="VPC to launch cluster in")
    subnets = p("Subnets", Type="List<AWS::EC2::Subnet::Id>", Description="Subnets for scaling group")
    p("EnvName", Type="String", Description="The name of the environment")

    #
    # Mappings
    #
    template.add_mapping(REGION_MAP, region_map())

    #
    # Resources
    #
    key = r(parameter_key(sceptre_user_data['ssm_key_admins']))
    node_role = r(node_instance_role(key))
    node_profile = r(node_instance_profile(node_role))
    fn_ex_role = r(lambda_execution_role())
    asg_lambda = r(lambda_fn_for_asg(fn_ex_role))
    sns_topic = r(asg_sns_topic(asg_lambda))
    sns_fn_role = r(sns_lambda_role())
    node_sg = r(node_security_group(vpc_id, sceptre_user_data['ingress_cidrs']))
    cluster = r(ecs_cluster())

    r(parameter_key_alias(key))
    r(service_role())
    r(lambda_invoke_permission(asg_lambda, sns_topic))
    r(lambda_subs_to_topic(asg_lambda, sns_topic))

    template.add_output(Output("ClusterArnOutput",
                               Value=Ref(cluster),
                               Export=Export(Sub("${EnvName}-EcsEnv-EcsCluster"))))

    for asg in sceptre_user_data['scaling_groups']:
        name = asg['name']
        sgs = [Ref(node_sg)] + sceptre_user_data['node_security_groups']
        c = r(launch_config(name, sgs, asg['node_type'], node_profile, asg['key_name']))
        asg = r(auto_scaling_group(name, subnets, c, asg['max_size'], asg['desired_size'], sns_topic))
        r(asg_terminate_hook(asg, sns_topic, sns_fn_role))

    return template.to_json()
