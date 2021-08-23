import hashlib
import os.path
import sys
import json
import re

from troposphere import Template, Ref, Sub, Parameter, GetAtt
from troposphere.cloudformation import AWSCustomObject
from troposphere.ecs import TaskDefinition, Service, ContainerDefinition, PortMapping, LogConfiguration, Environment, \
    LoadBalancer, DeploymentConfiguration, Volume, EFSVolumeConfiguration, MountPoint, Secret, PlacementStrategy
from troposphere.elasticloadbalancingv2 import ListenerRule, TargetGroup, Action, Condition, Matcher, \
    TargetGroupAttribute, PathPatternConfig, HostHeaderConfig
from troposphere.iam import Role, Policy
from troposphere.awslambda import Permission, Function, Code
from troposphere.events import Rule as EventRule, Target as EventTarget

from functools import reduce
from typing import List, Optional, Dict
from pydantic import BaseModel, ValidationError, validator


#
# IMPORTANT: The following classes are DATA CLASSES using pydantic.
#            DO NOT add behavior to them beyond input validation. Use functions
#            instead.
#


def debug(*args):
    print(*args, file=sys.stderr)


class PlacementStrategyModel(BaseModel):
    field: str
    type: str


class EfsVolumeModel(BaseModel):
    name: str
    fs_id: str
    root_directory: Optional[str]


class TargetGroupModel(BaseModel):
    attributes: Dict[str,str] = {}


class ScheduleModel(BaseModel):
    cron: str
    desired_count: int
    description = 'ECS service scheduling rule'


class RuleModel(BaseModel):
    path: str
    host: Optional[str]
    priority: Optional[int]


class PortMappingModel(BaseModel):
    container_port: int


class MountPointModel(BaseModel):
    container_path: str
    source_volume: str
    read_only = False


class HealthCheckModel(BaseModel):
    path: Optional[str]


class EnvironmentVariableModel(BaseModel):
    name: str
    value: str
    type = 'PLAINTEXT'

    @validator('type')
    def type_is_one_of(cls, v):
        allowed = ['PLAINTEXT', 'PARAMETER_STORE', 'SECRETS_MANAGER']
        if v in allowed:
            return v
        raise ValueError("Invalid type '{}' must be one of {}".format(v, allowed))


class ImageBuildModel(BaseModel):
    codebuild_project_name: str
    ecr_repo_name: str
    env_vars: List[EnvironmentVariableModel] = []


class ContainerModel(BaseModel):
    image: Optional[str]
    image_build: Optional[ImageBuildModel]
    container_port: Optional[int]
    port_mappings: List[PortMappingModel] = []
    container_memory = 512
    container_memory_reservation: Optional[int]
    env_vars: Dict[str,str] = {}
    health_check: Optional[HealthCheckModel]
    links: List[str] = []
    mount_points: List[MountPointModel] = []
    name = 'main'
    protocol = 'HTTP'
    rules: Optional[List[RuleModel]]
    secrets: Dict[str,str] = {}
    target_group = TargetGroupModel()
    target_group_arn: Optional[str]

    @validator('protocol')
    def protocol_one_of(cls, v):
        allowed = ['HTTP', 'HTTPS']
        if v not in allowed:
            raise ValueError("invalid protocol '{}' must be one of {}".format(v, allowed))
        return v

    @validator('image_build', always=True)
    def image_or_build(cls, v, values):
        if v is None:
            if not values.get('image', None):
                raise ValueError('container object must contain one of image or image_build')
        else:
            if values.get('image', None):
                raise ValueError('container object cannot have both image and image_build properties')
        return v

    @validator('target_group_arn', always=True)
    def port_or_mapping(cls, v, values):
        if v is not None or values['rules'] is not None:
            if len(values['port_mappings']) < 1:
                if not values.get('container_port', None):
                    raise ValueError('ELB-attached container object must contain one of container_port or port_mappings')
            else:
                if values.get('container_port', None):
                    raise ValueError('ELB-attached container object cannot have both container_port and port_mappings properties')
        return v


class UserDataModel(BaseModel):
    containers: List[ContainerModel]
    efs_volumes: List[EfsVolumeModel] = []
    placement_strategies: List[PlacementStrategyModel] = [PlacementStrategyModel(field='memory', type='binpack')]
    schedule: List[ScheduleModel] = []


TEMPLATE = Template()
PRIORITY_CACHE = []

TITLE_CHAR_MAP = {
    '-': 'DASH',
    '.': 'DOT',
    '_': 'US',
    '*': 'STAR',
    '?': 'QM',
    '/': 'SLASH',
    ' ': 'SP'
}


def as_list(s):
    """If s is a string it returns [s]. Otherwise it returns list(s)."""
    if isinstance(s, str):
        return [s]


def read_local_file(path):
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), path), 'r') as fp:
        return fp.read()


def add_resource(r):
    TEMPLATE.add_resource(r)
    return r


def add_resource_once(logical_id, res_fn):
    res = TEMPLATE.to_dict()['Resources']
    if logical_id in res:
        return res[logical_id]
    else:
        return add_resource(res_fn(logical_id))


def clean_title(s):
    for k in TITLE_CHAR_MAP.keys():
        s = s.replace(k, TITLE_CHAR_MAP[k])
    return s

    
def md5(s):
    return hashlib.md5(s.encode('utf-8')).hexdigest()


def priority_hash(rule):
    ret = int(md5(str(rule.dict(exclude_defaults=True, exclude_unset=True))), 16) % 48000 + 1000
    while ret in PRIORITY_CACHE:
        ret += 1
    PRIORITY_CACHE.append(ret)
    return ret


def add_params(t):
    t.add_parameter(Parameter("VpcId", Type="String"))
    t.add_parameter(Parameter("ListenerArn", Type="String"))
    t.add_parameter(Parameter("ClusterArn", Type="String"))
    t.add_parameter(Parameter("DesiredCount", Type="Number", Default="1"))
    t.add_parameter(Parameter("MaximumPercent", Type="Number", Default="200"))
    t.add_parameter(Parameter("MinimumHealthyPercent", Type="Number", Default="100"))


def execution_role_secret_statement(secret_arn):
    if ':secretsmanager:' in secret_arn:
        return {
            "Action": "secretsmanager:GetSecretValue",
            "Resource": secret_arn,
            "Effect": "Allow"
        }
    elif ':ssm:' in secret_arn:
        return {
            "Action": "ssm:GetParameters",
            "Resource": secret_arn,
            "Effect": "Allow"
        }
    else:
        return {
            "Action": "ssm:GetParameters",
            "Resource": Sub('arn:aws:ssm:${AWS::Region}:${AWS::AccountId}:parameter/%s' % secret_arn),
            "Effect": "Allow"
        }


def execution_role(secret_arns):
    return add_resource(Role('TaskExecutionRole',
                             AssumeRolePolicyDocument={
                                 "Version": "2012-10-17",
                                 "Statement": [{
                                     "Effect": "Allow",
                                     "Principal": {"Service": ["ecs-tasks.amazonaws.com"]},
                                     "Action": ['sts:AssumeRole']
                                 }]
                             },
                             ManagedPolicyArns=[
                                 'arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy'],
                             Policies=[
                                 Policy(
                                     PolicyName="root",
                                     PolicyDocument={
                                         "Version": '2012-10-17',
                                         "Statement": [
                                             {"Effect": "Allow",
                                              "Action": ["logs:CreateLogGroup",
                                                         "logs:CreateLogStream",
                                                         "logs:PutLogEvents",
                                                         "logs:DescribeLogStreams"],
                                              "Resource": ['arn:aws:logs:*:*:*']}]
                                     }
                                 ),
                                 Policy(
                                     PolicyName="secrets",
                                     PolicyDocument={
                                         "Version": '2012-10-17',
                                         "Statement": [execution_role_secret_statement(s) for s in secret_arns]
                                     }
                                 )
                             ]))


def container_mount_point(data):
    return MountPoint(ContainerPath=data.container_path,
                      SourceVolume=data.source_volume,
                      ReadOnly=data.read_only)


def port_mappings(container_data):
    if len(container_data.port_mappings) > 0:
        return [PortMapping(ContainerPort=m.container_port) for m in container_data.port_mappings]
    elif container_data.container_port:
        return [PortMapping(ContainerPort=container_data.container_port)]
    else:
        return []


def lambda_fn_for_codebuild():
    lambda_execution_role()
    return add_resource_once("LambdaFunctionForCodeBuild", lambda name: Function(
        name,
        Description="Builds a container image",
        Handler="index.lambda_handler",
        Role=GetAtt('LambdaExecutionRole', "Arn"),
        Runtime="python3.6",
        MemorySize=128,
        Timeout=900,
        Code=Code(ZipFile=Sub(read_local_file("EcsWebService_CodeBuildResourceLambda.py")))
    ))


class ImageBuild(AWSCustomObject):
    resource_type = "Custom::ImageBuild"
    props = {"ServiceToken": (str, True),
             "ProjectName": (str, True),
             "EnvironmentVariablesOverride": (list, False),
             "RepositoryName": (str, False)}


def image_build(container_name, build):
    lambda_fn_for_codebuild()
    return add_resource(ImageBuild(
        "ImageBuildFor{}".format(container_name),
        ServiceToken=GetAtt('LambdaFunctionForCodeBuild', 'Arn'),
        ProjectName=build.codebuild_project_name,
        EnvironmentVariablesOverride=[v.dict() for v in build.env_vars],
        RepositoryName=build.ecr_repo_name
    ))


def container_def(container):
    # NB: container_memory is the hard limit on RAM presented to the container. It will be killed if it tries to
    #     allocate more. container_memory_reservation is the soft limit and docker will try to keep the container to
    #     this value.
    #
    # TODO: container_memory_reservation is not mandatory. Maybe it should default to undefined?
    container_memory = container.container_memory
    container_memory_reservation = container.container_memory_reservation if container.container_memory_reservation else container.container_memory

    # Base environment variables from the stack
    env_map = {
        "AWS_DEFAULT_REGION": Ref("AWS::Region")
    }

    # Add stack-specific vars
    env_map.update(container.env_vars)

    # Convert the environment map to a list of Environment objects
    environment = [Environment(Name=k, Value=v) for (k, v) in env_map.items()]

    # Convert the secrets map into a list of Secret objects
    secrets = [Secret(Name=k, ValueFrom=v) for (k, v) in container.secrets.items()]

    # Configure mount points
    mount_points = [container_mount_point(p) for p in container.mount_points]

    if container.image_build is not None:
        image = GetAtt(image_build(container.name, container.image_build), 'ImageURI')
    else:
        image = container.image

    return ContainerDefinition(
        Name=container.name,
        Environment=environment,
        Secrets=secrets,
        Essential=True,
        Hostname=Ref("AWS::StackName"),
        Image=image,
        Memory=container_memory,
        MemoryReservation=container_memory_reservation,
        MountPoints=mount_points,
        PortMappings=port_mappings(container),
        Links=container.links,

        # TODO: We might want to check for failed connection pools and this can probably be done
        #       using HealthCheck here which runs a command inside the container.

        LogConfiguration=LogConfiguration(
            LogDriver="awslogs",
            Options={
                "awslogs-group": Sub("/ecs/${AWS::StackName}"),
                "awslogs-region": Ref("AWS::Region"),
                "awslogs-stream-prefix": "ecs",
                "awslogs-create-group": True
            }
        ))


def efs_volume(v):
    extra_args = {}
    if v.root_directory:
        extra_args['RootDirectory'] = v.root_directory

    return Volume(Name=v.name,
                  EFSVolumeConfiguration=EFSVolumeConfiguration(FilesystemId=v["fs_id"], **extra_args))


def task_def(container_defs, efs_volumes, exec_role):
    volumes = [efs_volume(v) for v in efs_volumes]

    extra_args = {}
    if exec_role is not None:
        extra_args['ExecutionRoleArn'] = Ref(exec_role)

    return add_resource(TaskDefinition("TaskDef",
                                       Volumes=volumes,
                                       Family=Ref("AWS::StackName"),
                                       ContainerDefinitions=container_defs,
                                       **extra_args))


def target_group(protocol, health_check, target_group_props, default_health_check_path):
    health_check_path = health_check.path if health_check and health_check.path else default_health_check_path
    attrs = target_group_props.attributes

    if 'stickiness.enabled' not in attrs:
        attrs['stickiness.enabled'] = 'true'
    if 'stickiness.type' not in attrs:
        attrs['stickiness.type'] = 'lb_cookie'

    return add_resource(TargetGroup(clean_title("TargetGroupFOR%s" % health_check_path),
                                    HealthCheckProtocol=protocol,
                                    HealthCheckPath=health_check_path,

                                    HealthCheckIntervalSeconds=60,
                                    HealthCheckTimeoutSeconds=30,
                                    UnhealthyThresholdCount=5,

                                    Matcher=Matcher(HttpCode="200-399"),
                                    Port=8080,  # This is overridden by the targets themselves.
                                    Protocol=protocol,
                                    TargetGroupAttributes=[TargetGroupAttribute(Key=k, Value=str(v))
                                                           for k, v in attrs.items()],
                                    TargetType="instance",
                                    VpcId=Ref("VpcId")))


def listener_rule(tg, rule):
    path = rule.path
    priority = rule.priority if rule.priority else priority_hash(rule)

    # TODO: We may want to support more flexible rules in the way
    #       MultiHostElb.py does. But one thing to note if we do that, rules
    #       having a single path and no host would need to have their priority
    #       hash generated as above (priority_hash(path)). Otherwise it'll cause
    #       issues when updating older stacks.
    if path == '/':
        conditions = []
    else:
        path_patterns = [path, "%s/*" % path]
        conditions = [Condition(Field="path-pattern", PathPatternConfig=PathPatternConfig(Values=path_patterns))]

    if rule.host:
        conditions.append(Condition(
            Field='host-header',
            HostHeaderConfig=HostHeaderConfig(Values=[rule.host])))

    return add_resource(ListenerRule("ListenerRule%s" % priority,
                                     Actions=[Action(
                                         Type="forward",
                                         TargetGroupArn=Ref(tg))],
                                     Conditions=conditions,
                                     ListenerArn=Ref("ListenerArn"),
                                     Priority=priority))


def service(listener_rules, lb_mappings, placement_strategies):
    return add_resource(Service("Service",
                                DependsOn=[r.title for r in listener_rules],
                                TaskDefinition=Ref("TaskDef"),
                                Cluster=Ref('ClusterArn'),
                                DesiredCount=Ref("DesiredCount"),
                                PlacementStrategies=[PlacementStrategy(Field=s.field, Type=s.type)
                                                     for s in placement_strategies],
                                DeploymentConfiguration=DeploymentConfiguration(
                                    MaximumPercent=Ref("MaximumPercent"),
                                    MinimumHealthyPercent=Ref("MinimumHealthyPercent")),
                                LoadBalancers=lb_mappings))


def lambda_execution_role():
    # TODO: See if we can tighten this a bit.
    return add_resource_once("LambdaExecutionRole", lambda name: Role(
        name,
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
                        "ecr:DescribeImages",
                        "ecr:DescribeRepositories",
                        "ecr:ListImages",
                        "codebuild:StartBuild",
                        "codebuild:BatchGetBuilds",
                        "ecs:UpdateService"
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
        ManagedPolicyArns=[],
        Path="/"
    ))


def scheduling_lambda():
    return add_resource(Function(
        "SchedulingLambda",
        Description="Updates service properties on a schedule",
        Handler="index.lambda_handler",
        Role=GetAtt('LambdaExecutionRole', "Arn"),
        Runtime="python3.6",
        MemorySize=128,
        Timeout=60,
        Code=Code(ZipFile=Sub(read_local_file("EcsWebService_ScheduleLambda.py")))
    ))


def lambda_invoke_permission(rule):
    return add_resource(Permission(
        "LambdaInvokePermission" + rule.title,
        FunctionName=Ref('SchedulingLambda'),
        Action="lambda:InvokeFunction",
        Principal="events.amazonaws.com",
        SourceArn=GetAtt(rule, 'Arn')
    ))


def scheduling_rule(rule_props):
    cron_expr = rule_props.cron
    rule_hash = md5(cron_expr)[:7]
    desired_count = rule_props.desired_count

    return add_resource(EventRule(
        'ScheduleRule' + rule_hash,
        ScheduleExpression='cron(%s)' % cron_expr,
        Description=rule_props.description,
        Targets=[EventTarget(
            Id='ScheduleRule' + rule_hash,
            Arn=GetAtt('SchedulingLambda', 'Arn'),
            Input=json.dumps({'desired_count': desired_count})
        )]
    ))


def sceptre_handler(sceptre_user_data):
    add_params(TEMPLATE)

    user_data = UserDataModel(**sceptre_user_data)
    efs_volumes = user_data.efs_volumes

    # If we're using secrets, we need to define an execution role
    secret_arns = [v for c in user_data.containers for k, v in c.secrets.items()]
    exec_role = execution_role(secret_arns) if len(secret_arns) > 0 else None

    containers = []
    listener_rules = []
    lb_mappings = []
    for c in user_data.containers:
        container = container_def(c)
        containers.append(container)

        if c.target_group_arn:
            # We're injecting into an existing target. Don't set up listener rules.
            target_group_arn = c.target_group_arn
        elif c.rules:
            # Create target group and associated listener rules
            tg = target_group(c.protocol, c.health_check, c.target_group, "%s/" % c.rules[0].path)

            for rule in c.rules:
                listener_rules.append(listener_rule(tg, rule))

            target_group_arn = Ref(tg)
        else:
            target_group_arn = None

        if target_group_arn is not None:
            if len(container.PortMappings) < 1:
                raise ValueError(
                    "Container '%s' connects to an ELB but does not specify port_mappings or container_port" % c['name'])
            lb_mappings.append(LoadBalancer(ContainerName=container.Name,
                                            # TODO: Ugly hack, do better.
                                            ContainerPort=container.PortMappings[0].ContainerPort,
                                            TargetGroupArn=target_group_arn))

    task_def(containers, efs_volumes, exec_role)
    service(listener_rules, lb_mappings, user_data.placement_strategies)

    schedule = user_data.schedule
    if len(schedule) > 0:
        lambda_execution_role()
        scheduling_lambda()
        for p in schedule:
            rule = scheduling_rule(p)
            lambda_invoke_permission(rule)

    return TEMPLATE.to_json()
