import hashlib
import os.path
import sys
import json
import re

from troposphere import Template, Ref, Sub, Parameter, GetAtt, Tags
from troposphere.cloudformation import AWSCustomObject
from troposphere.ecs import (
    ContainerDefinition,
    ContainerDependency,
    DeploymentConfiguration,
    EFSVolumeConfiguration,
    Environment,
    LinuxParameters,
    LoadBalancer,
    LogConfiguration,
    MountPoint,
    PlacementStrategy,
    PortMapping,
    Secret,
    Service,
    TaskDefinition,
    Volume,
    HealthCheck as ContainerHealthCheck,
)
from troposphere.elasticloadbalancingv2 import (
    ListenerRule,
    TargetGroup,
    Action,
    Condition,
    Matcher,
    TargetGroupAttribute,
    PathPatternConfig,
    HostHeaderConfig,
)
from troposphere.iam import Role, Policy
from troposphere.awslambda import Permission, Function, Code
from troposphere.events import Rule as EventRule, Target as EventTarget

from typing import List, Optional, Dict
from pydantic import BaseModel, ValidationError, validator, Field


#
# IMPORTANT: The following classes are DATA CLASSES using pydantic.
#            DO NOT add behavior to them beyond input validation. Use functions
#            instead.
#


def debug(*args):
    print(*args, file=sys.stderr)


class PlacementStrategyModel(BaseModel):
    """**See:** [AWS::ECS::Service PlacementStrategy](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-ecs-service-placementstrategy.html)
    for more information."""

    field: str = Field(description="The field to apply the placement strategy against")
    type: str = Field(description="The type of placement strategy")


class EfsVolumeModel(BaseModel):
    name: str = Field(
        description="""This is the name which will be referred to by `source_volume` values defined in the
                       `mount_points` settings of a container."""
    )
    fs_id: str = Field(description="The ID of the EFS volume")
    root_directory: Optional[str] = Field(
        description="The directory within the EFS volume which will mounted by containers",
        default_description="By default the root directory of the volume will be used.",
    )


class TargetGroupModel(BaseModel):
    attributes: Dict[str, str] = Field(
        {},
        description="Sets target group attributes",
        default_description="""The following attributes are defined by default:
    * `'stickiness.enabled' = 'true'`
    * `'stickiness.type' = 'lb_cookie'`""",
        notes=[
            "**See Also:** [AWS::ElasticLoadBalancingV2::TargetGroup TargetGroupAttribute](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-elasticloadbalancingv2-targetgroup-targetgroupattribute.html)"
        ],
    )


class ScheduleModel(BaseModel):
    cron: str = Field(
        description="""Cron expression for when this schedule fires. Only cron expressions are
                       supported and the `cron()` clause is implied. So values
                       should be specified like `0 0 * * ? *` instead of `cron(0
                       12 * * ? *)`.""",
        notes=[
            """AWS requires that all cron expressions be in UTC. It is not possible at this
               time to specify a local timezone. You will therefore need to
               adjust your cron expressions appropriately.""",
            "**See Also:** [Schedule Expressions for Rules](https://docs.aws.amazon.com/AmazonCloudWatch/latest/events/ScheduledEvents.html#CronExpressions)",
        ],
    )
    desired_count: int = Field(
        description="Desired number of tasks to set for the service at the specified time."
    )
    description = Field(
        "ECS service scheduling rule",
        description="Description of the schedule",
        omit_default=True,
    )


class RuleModel(BaseModel):
    path: str = Field(
        description="""The context path for the listener rule. The path should start with a `/`. Two
                       listener rules will be created, one matching `path` and
                       one matching `path + '/*'`."""
    )
    host: Optional[str] = Field(
        description="""Pattern to match against the request's host header. Wildcards `?` and `*` are supported.""",
        notes=[
            "For this setting to work properly, the ELB will need to be set up to for multiple hostnames.",
            "**See Also:** [AWS::ElasticLoadBalancingV2::ListenerRule HostHeaderConfig](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-elasticloadbalancingv2-listenerrule-hostheaderconfig.html)",
        ],
    )
    priority: Optional[int] = Field(
        description="The priority value for the listener rule. If undefined, a hash-based value will be generated."
    )


class PortMappingModel(BaseModel):
    container_port: int = Field(
        description="The port exposed by the container",
        notes=[
            """You may specify more than one port mapping object per container, but the
               target group will always route its traffic to the
               `container_port` of the first port mapping."""
        ],
    )


class MountPointModel(BaseModel):
    container_path: str = Field(
        description="The mount point for the volume within the container"
    )
    source_volume: str = Field(
        description="The `name` value specified for the volume in `sceptre_user_data.efs_volumes`."
    )
    read_only = Field(
        False, description="If true, the volume will not be writable to the container."
    )


class HealthCheckModel(BaseModel):
    path: Optional[str] = Field(
        description="Path the target group health check will request",
        default_desc="If unspecified, the `path` value of the first [rule](#rule-objects) will be used.",
    )
    interval_seconds = Field(
        60,
        description="The approximate amount of time between health checks of an individual target.",
    )
    timeout_seconds = Field(
        30,
        description="The amount of time during which no response from a target means a failed health check.",
    )
    healthy_threshold_count: Optional[int] = Field(
        description="""The number of consecutive health checks successes required before considering
                       an unhealthy target healthy."""
    )
    unhealthy_threshold_count = Field(
        5,
        description="""The number of consecutive health check failures required before considering a
                       target unhealthy.""",
    )
    http_code = Field(
        "200-399",
        description="""HTTP status code(s) the health check will consider "healthy." You can specify
                       values between 200 and 499, and the default value is 200.
                       You can specify multiple values (for example, "200,202")
                       or a range of values (for example, "200-299").""",
    )


class EnvironmentVariableModel(BaseModel):
    name: str
    value: str
    type = Field(
        "PLAINTEXT",
        notes=["**Allowed Values:** `PLAINTEXT`, `PARAMETER_STORE`, `SECRETS_MANAGER`"],
    )

    @validator("type")
    def type_is_one_of(cls, v):
        allowed = ["PLAINTEXT", "PARAMETER_STORE", "SECRETS_MANAGER"]
        if v in allowed:
            return v
        raise ValueError("Invalid type '{}' must be one of {}".format(v, allowed))


class ImageBuildModel(BaseModel):
    codebuild_project_name: str = Field(
        description="""Name of the CodeBuild project which builds the image."""
    )
    ecr_repo_name: str = Field(
        description="Name of the ECR repo into which the build image will be pushed."
    )
    env_vars: List[EnvironmentVariableModel] = Field(
        [], description="Environment variable overrides for the build."
    )


class ContainerModel(BaseModel):
    image: Optional[str] = Field(
        description="The URI of the container image.",
        notes=[
            "**Requirement:** One of `image` or `image_build` must be defined",
            "[AWS::ECS::TaskDefinition ContainerDefinition](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-ecs-taskdefinition-containerdefinitions.html#cfn-ecs-taskdefinition-containerdefinition-image)",
        ],
    )
    image_build: Optional[ImageBuildModel] = Field(
        description="Settings for building the container image.",
        notes=["**Requirement:** One of `image` or `image_build` must be defined"],
    )
    command: List[str] = Field(
        [],
        description="Maps to the COMMAND parameter of [docker run](https://docs.docker.com/engine/reference/run/#security-configuration).",
    )
    container_port: Optional[int] = Field(
        description="The port exposed by the container",
        notes=[
            "One of `container_port` or `port_mappings` must be defined for any container connecting to an ELB."
        ],
    )
    port_mappings: List[PortMappingModel] = Field(
        [],
        description="List of port-mappings to assign to the container.",
        notes=[
            "**Requirement:** One of `container_port` or `port_mappings` must be defined for any container connecting to an ELB."
        ],
    )
    container_memory = Field(
        512,
        description="""The amount (in MiB) of memory to present to the container. If your container
                       attempts to exceed the memory specified here, the
                       container is killed.""",
        notes=[
            """If you specify both `container_memory` and `container_memory_reservation`,
               `container_memory` must be greater than
               `container_memory_reservation`. If you specify
               `container_memory_reservation`, then that value is subtracted
               from the available memory resources for the container instance on
               which the container is placed. Otherwise, the value of
               `container_memory` is used."""
        ],
    )
    container_memory_reservation: Optional[int] = Field(
        description="The soft limit (in MiB) of memory to reserve for the container.",
        notes=[
            """If you specify both `container_memory` and `container_memory_reservation`,
               `container_memory` must be greater than
               `container_memory_reservation`. If you specify
               `container_memory_reservation`, then that value is subtracted
               from the available memory resources for the container instance on
               which the container is placed. Otherwise, the value of
               `container_memory` is used."""
        ],
    )
    env_vars: Dict[str, str] = Field(
        {}, description="Environment variables passed to the container."
    )
    health_check: Optional[HealthCheckModel] = Field(
        description="""Defines the health check for the target group. If `rules` is not specified
                       for the container, this setting has no effect."""
    )
    container_health_check: Optional[dict] = Field(
        description="""Container health check as defined in [AWS::ECS::TaskDefinition HealthCheck](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-ecs-taskdefinition-healthcheck.html)"""
    )
    depends_on: Optional[List[dict]] = Field(
        description="""List of container dependencies as defined in [AWS::ECS::TaskDefinition ContainerDependency](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-ecs-taskdefinition-containerdependency.html)"""
    )
    links: List[str] = Field(
        [],
        description="""List of container `names` to which to link this container. The `links`
                       parameter allows containers to communicate with each
                       other without the need for port mappings.""",
        notes=[
            "**See Also:** [AWS::ECS::TaskDefinition ContainerDefinition](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-ecs-taskdefinition-containerdefinitions.html#cfn-ecs-taskdefinition-containerdefinition-links)"
        ],
    )
    mount_points: List[MountPointModel] = Field(
        [],
        description="Maps volumes defined in `sceptre_user_data.efs_volumes` to mount points within the container.",
    )
    name = Field("main", description="The name of the container")
    protocol = Field(
        "HTTP",
        description="The back-end protocol used by the load-balancer to communicate with the container",
    )
    rules: Optional[List[RuleModel]] = Field(
        description="""If specified, the stack will create an ELB target group and add the specified
                       rules to the listener to route traffic."""
    )
    secrets: Dict[str, str] = Field(
        {},
        description="""Secrets passed as environment variables to the container. The key will
                       specify the variable being set. The value specifies where
                       ECS should read the value from.""",
        notes=[
            """The supported values are either the full ARN of the AWS Secrets Manager
                  secret or the full ARN of the parameter in the SSM Parameter
                  Store. If the SSM Parameter Store parameter exists in the same
                  Region as the task you are launching, then you can use either
                  the full ARN or name of the parameter. If the parameter exists
                  in a different Region, then the full ARN must be specified."""
        ],
    )
    target_group = Field(
        TargetGroupModel(),
        description="""Extended options for the target group. If `rules` is not specified for the
                       container, this setting has no effect.""",
    )
    target_group_arn: Optional[str] = Field(
        description="""ARN of the ELB target group to for the container. If this option is specified
                       instead of `rules` then no target group will be created.
                       Instead, the container will be assigned to an
                       externally-defined target group. This is normally used to
                       assign a container to the default target group of an
                       ELB."""
    )
    linux_parameters: Dict = Field(
        {},
        description="Linux-specific options that are applied to the container",
        notes=[
            "**See Also:** [AWS::ECS::TaskDefinition LinuxParameters](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-ecs-taskdefinition-linuxparameters.html#cfn-ecs-taskdefinition-linuxparameters-sharedmemorysize)"
        ],
    )
    container_extra_props: Dict = Field(
        {},
        description="Additional options to include in the ContainerDefinition",
        notes=[
            "**See Also:** [AWS::ECS::TaskDefinition ContainerDefinition](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-ecs-taskdefinition-containerdefinitions.html)"
        ],
    )

    @validator("image_build", always=True)
    def image_or_build(cls, v, values):
        if v is None:
            if not values.get("image", None):
                raise ValueError(
                    "container object must contain one of image or image_build"
                )
        else:
            if values.get("image", None):
                raise ValueError(
                    "container object cannot have both image and image_build properties"
                )
        return v

    @validator("target_group_arn", always=True)
    def port_or_mapping(cls, v, values):
        if v is not None or values["rules"] is not None:
            if len(values["port_mappings"]) < 1:
                if not values.get("container_port", None):
                    raise ValueError(
                        "ELB-attached container object must contain one of container_port or port_mappings"
                    )
            else:
                if values.get("container_port", None):
                    raise ValueError(
                        "ELB-attached container object cannot have both container_port and port_mappings properties"
                    )
        return v


class UserDataModel(BaseModel):
    service_tags: Dict[str, str] = {}
    containers: List[ContainerModel] = Field(
        description="Defines the containers for this service."
    )
    efs_volumes: List[EfsVolumeModel] = Field(
        [],
        description="Set of EFS volumes to make available to containers within this service.",
        notes=[
            "To make an EFS volume available to a container you must define it in the `efs_volumes` setting and define an entry in the `mount_points` setting within the container object."
        ],
    )
    placement_strategies: List[PlacementStrategyModel] = Field(
        [PlacementStrategyModel(field="memory", type="binpack")],
        description="Defines the set of placement strategies for service tasks.",
    )
    schedule: List[ScheduleModel] = Field(
        [],
        description="Specifies a schedule for modifying the DesiredCount of the service.",
    )


TEMPLATE = Template()
PRIORITY_CACHE = []

TITLE_CHAR_MAP = {
    "-": "DASH",
    ".": "DOT",
    "_": "US",
    "*": "STAR",
    "?": "QM",
    "/": "SLASH",
    " ": "SP",
}


def as_list(s):
    """If s is a string it returns [s]. Otherwise it returns list(s)."""
    if isinstance(s, str):
        return [s]


def read_local_file(path):
    with open(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), path), "r"
    ) as fp:
        return fp.read()


def add_resource(r):
    TEMPLATE.add_resource(r)
    return r


def add_resource_once(logical_id, res_fn):
    res = TEMPLATE.to_dict()["Resources"]
    if logical_id in res:
        return res[logical_id]
    else:
        return add_resource(res_fn(logical_id))


def clean_title(s):
    for k in TITLE_CHAR_MAP.keys():
        s = s.replace(k, TITLE_CHAR_MAP[k])
    return s


def md5(s):
    return hashlib.md5(s.encode("utf-8")).hexdigest()


def priority_hash(rule):
    ret = (
        int(md5(str(rule.dict(exclude_defaults=True, exclude_unset=True))), 16) % 48000
        + 1000
    )
    while ret in PRIORITY_CACHE:
        ret += 1
    PRIORITY_CACHE.append(ret)
    return ret


def add_params(t):
    t.add_parameter(
        Parameter(
            "VpcId", Type="String", Description="The ID of the VPC of the ECS cluster"
        )
    )
    t.add_parameter(
        Parameter(
            "ListenerArn",
            Type="String",
            Description="The ARN of the ELB listener which will be used by this service",
        )
    )
    t.add_parameter(
        Parameter(
            "ClusterArn",
            Type="String",
            Description="The ARN or name of the ECS cluster",
        )
    )
    t.add_parameter(
        Parameter(
            "DesiredCount",
            Type="Number",
            Default="1",
            Description="The desired number of instances of this service",
        )
    )
    t.add_parameter(
        Parameter(
            "MaximumPercent",
            Type="Number",
            Default="200",
            Description="The maximum percent of `DesiredCount` allowed to be running during updates.",
        )
    )
    t.add_parameter(
        Parameter(
            "MinimumHealthyPercent",
            Type="Number",
            Default="100",
            Description="The minimum number of running instances of this service to keep running during an update.",
        )
    )


def execution_role_secret_statement(secret_arn):
    if ":secretsmanager:" in secret_arn:
        return {
            "Action": "secretsmanager:GetSecretValue",
            "Resource": secret_arn,
            "Effect": "Allow",
        }
    elif ":ssm:" in secret_arn:
        return {
            "Action": "ssm:GetParameters",
            "Resource": secret_arn,
            "Effect": "Allow",
        }
    else:
        return {
            "Action": "ssm:GetParameters",
            "Resource": Sub(
                "arn:aws:ssm:${AWS::Region}:${AWS::AccountId}:parameter/%s" % secret_arn
            ),
            "Effect": "Allow",
        }


def execution_role(secret_arns):
    return add_resource(
        Role(
            "TaskExecutionRole",
            AssumeRolePolicyDocument={
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"Service": ["ecs-tasks.amazonaws.com"]},
                        "Action": ["sts:AssumeRole"],
                    }
                ],
            },
            ManagedPolicyArns=[
                "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
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
                                    "logs:CreateLogGroup",
                                    "logs:CreateLogStream",
                                    "logs:PutLogEvents",
                                    "logs:DescribeLogStreams",
                                ],
                                "Resource": ["arn:aws:logs:*:*:*"],
                            }
                        ],
                    },
                ),
                Policy(
                    PolicyName="secrets",
                    PolicyDocument={
                        "Version": "2012-10-17",
                        "Statement": [
                            execution_role_secret_statement(s) for s in secret_arns
                        ],
                    },
                ),
            ],
        )
    )


def container_mount_point(data):
    return MountPoint(
        ContainerPath=data.container_path,
        SourceVolume=data.source_volume,
        ReadOnly=data.read_only,
    )


def port_mappings(container_data):
    if len(container_data.port_mappings) > 0:
        return [
            PortMapping(ContainerPort=m.container_port)
            for m in container_data.port_mappings
        ]
    elif container_data.container_port:
        return [PortMapping(ContainerPort=container_data.container_port)]
    else:
        return []


def lambda_fn_for_codebuild():
    lambda_execution_role()
    return add_resource_once(
        "LambdaFunctionForCodeBuild",
        lambda name: Function(
            name,
            Description="Builds a container image",
            Handler="index.lambda_handler",
            Role=GetAtt("LambdaExecutionRole", "Arn"),
            Runtime="python3.6",
            MemorySize=128,
            Timeout=900,
            Code=Code(
                ZipFile=Sub(read_local_file("EcsWebService_CodeBuildResourceLambda.py"))
            ),
        ),
    )


class ImageBuild(AWSCustomObject):
    resource_type = "Custom::ImageBuild"
    props = {
        "ServiceToken": (str, True),
        "ProjectName": (str, True),
        "EnvironmentVariablesOverride": (list, False),
        "RepositoryName": (str, False),
    }


def image_build(container_name, build):
    lambda_fn_for_codebuild()
    return add_resource(
        ImageBuild(
            "ImageBuildFor{}".format(container_name),
            ServiceToken=GetAtt("LambdaFunctionForCodeBuild", "Arn"),
            ProjectName=build.codebuild_project_name,
            EnvironmentVariablesOverride=[v.dict() for v in build.env_vars],
            RepositoryName=build.ecr_repo_name,
        )
    )


def container_def(container):
    # NB: container_memory is the hard limit on RAM presented to the container. It will be killed if it tries to
    #     allocate more. container_memory_reservation is the soft limit and docker will try to keep the container to
    #     this value.
    #
    # TODO: container_memory_reservation is not mandatory. Maybe it should default to undefined?
    container_memory = container.container_memory
    container_memory_reservation = (
        container.container_memory_reservation
        if container.container_memory_reservation
        else container.container_memory
    )

    # Base environment variables from the stack
    env_map = {"AWS_DEFAULT_REGION": Ref("AWS::Region")}

    # Add stack-specific vars
    env_map.update(container.env_vars)

    # Convert the environment map to a list of Environment objects
    environment = [Environment(Name=k, Value=v) for (k, v) in env_map.items()]

    # Convert the secrets map into a list of Secret objects
    secrets = [Secret(Name=k, ValueFrom=v) for (k, v) in container.secrets.items()]

    # Configure mount points
    mount_points = [container_mount_point(p) for p in container.mount_points]

    if container.image_build is not None:
        image = GetAtt(image_build(container.name, container.image_build), "ImageURI")
    else:
        image = container.image

    extra_args = {}
    if len(container.linux_parameters) > 0:
        extra_args["LinuxParameters"] = LinuxParameters(**container.linux_parameters)
    if len(container.command) > 0:
        extra_args["Command"] = container.command
    if container.depends_on:
        extra_args["DependsOn"] = [
            ContainerDependency(**d) for d in container.depends_on
        ]
    if container.container_health_check:
        extra_args["HealthCheck"] = ContainerHealthCheck(
            **container.container_health_check
        )

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
                "awslogs-create-group": True,
            },
        ),
        **extra_args,
        **container.container_extra_props
    )


def efs_volume(v):
    extra_args = {}
    if v.root_directory:
        extra_args["RootDirectory"] = v.root_directory

    return Volume(
        Name=v.name,
        EFSVolumeConfiguration=EFSVolumeConfiguration(
            FilesystemId=v.fs_id, **extra_args
        ),
    )


def task_def(container_defs, efs_volumes, exec_role):
    volumes = [efs_volume(v) for v in efs_volumes]

    extra_args = {}
    if exec_role is not None:
        extra_args["ExecutionRoleArn"] = Ref(exec_role)

    return add_resource(
        TaskDefinition(
            "TaskDef",
            Volumes=volumes,
            Family=Ref("AWS::StackName"),
            ContainerDefinitions=container_defs,
            **extra_args
        )
    )


def target_group(protocol, health_check, target_group_props, default_health_check_path):
    if not health_check:
        health_check = HealthCheckModel()
    if not health_check.path:
        health_check.path = default_health_check_path
    attrs = target_group_props.attributes

    if "stickiness.enabled" not in attrs:
        attrs["stickiness.enabled"] = "true"
    if "stickiness.type" not in attrs:
        attrs["stickiness.type"] = "lb_cookie"

    extra_args = {}
    if health_check.healthy_threshold_count:
        extra_args["HealthyThresholdCount"] = health_check.healthy_threshold_count

    return add_resource(
        TargetGroup(
            clean_title("TargetGroupFOR%s" % health_check.path),
            HealthCheckProtocol=protocol,
            HealthCheckPath=health_check.path,
            HealthCheckIntervalSeconds=health_check.interval_seconds,
            HealthCheckTimeoutSeconds=health_check.timeout_seconds,
            UnhealthyThresholdCount=health_check.unhealthy_threshold_count,
            Matcher=Matcher(HttpCode=health_check.http_code),
            Port=8080,  # This is overridden by the targets themselves.
            Protocol=protocol,
            TargetGroupAttributes=[
                TargetGroupAttribute(Key=k, Value=str(v)) for k, v in attrs.items()
            ],
            TargetType="instance",
            VpcId=Ref("VpcId"),
            **extra_args
        )
    )


def listener_rule(tg, rule):
    path = rule.path
    priority = rule.priority if rule.priority else priority_hash(rule)

    # TODO: We may want to support more flexible rules in the way
    #       MultiHostElb.py does. But one thing to note if we do that, rules
    #       having a single path and no host would need to have their priority
    #       hash generated as above (priority_hash(path)). Otherwise it'll cause
    #       issues when updating older stacks.
    if path == "/":
        conditions = []
    else:
        path_patterns = [path, "%s/*" % path]
        conditions = [
            Condition(
                Field="path-pattern",
                PathPatternConfig=PathPatternConfig(Values=path_patterns),
            )
        ]

    if rule.host:
        conditions.append(
            Condition(
                Field="host-header",
                HostHeaderConfig=HostHeaderConfig(Values=[rule.host]),
            )
        )

    return add_resource(
        ListenerRule(
            "ListenerRule%s" % priority,
            Actions=[Action(Type="forward", TargetGroupArn=Ref(tg))],
            Conditions=conditions,
            ListenerArn=Ref("ListenerArn"),
            Priority=priority,
        )
    )


def service(tags, listener_rules, lb_mappings, placement_strategies):
    opts = {}
    if len(tags) > 0:
        opts["Tags"] = Tags(**tags)

    return add_resource(
        Service(
            "Service",
            DependsOn=[r.title for r in listener_rules],
            TaskDefinition=Ref("TaskDef"),
            Cluster=Ref("ClusterArn"),
            DesiredCount=Ref("DesiredCount"),
            PlacementStrategies=[
                PlacementStrategy(Field=s.field, Type=s.type)
                for s in placement_strategies
            ],
            DeploymentConfiguration=DeploymentConfiguration(
                MaximumPercent=Ref("MaximumPercent"),
                MinimumHealthyPercent=Ref("MinimumHealthyPercent"),
            ),
            LoadBalancers=lb_mappings,
            **opts
        )
    )


def lambda_execution_role():
    # TODO: See if we can tighten this a bit.
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
                                    "ecr:DescribeImages",
                                    "ecr:DescribeRepositories",
                                    "ecr:ListImages",
                                    "codebuild:StartBuild",
                                    "codebuild:BatchGetBuilds",
                                    "ecs:UpdateService",
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
            ManagedPolicyArns=[],
            Path="/",
        ),
    )


def scheduling_lambda():
    return add_resource(
        Function(
            "SchedulingLambda",
            Description="Updates service properties on a schedule",
            Handler="index.lambda_handler",
            Role=GetAtt("LambdaExecutionRole", "Arn"),
            Runtime="python3.6",
            MemorySize=128,
            Timeout=60,
            Code=Code(ZipFile=Sub(read_local_file("EcsWebService_ScheduleLambda.py"))),
        )
    )


def lambda_invoke_permission(rule):
    return add_resource(
        Permission(
            "LambdaInvokePermission" + rule.title,
            FunctionName=Ref("SchedulingLambda"),
            Action="lambda:InvokeFunction",
            Principal="events.amazonaws.com",
            SourceArn=GetAtt(rule, "Arn"),
        )
    )


def scheduling_rule(rule_props):
    cron_expr = rule_props.cron
    rule_hash = md5(cron_expr)[:7]
    desired_count = rule_props.desired_count

    return add_resource(
        EventRule(
            "ScheduleRule" + rule_hash,
            ScheduleExpression="cron(%s)" % cron_expr,
            Description=rule_props.description,
            Targets=[
                EventTarget(
                    Id="ScheduleRule" + rule_hash,
                    Arn=GetAtt("SchedulingLambda", "Arn"),
                    Input=json.dumps({"desired_count": desired_count}),
                )
            ],
        )
    )


def sceptre_handler(sceptre_user_data):
    add_params(TEMPLATE)

    if sceptre_user_data is None:
        # We're generating documetation. Return the template with just parameters.
        return TEMPLATE

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
            tg = target_group(
                c.protocol, c.health_check, c.target_group, "%s/" % c.rules[0].path
            )

            for rule in c.rules:
                listener_rules.append(listener_rule(tg, rule))

            target_group_arn = Ref(tg)
        else:
            target_group_arn = None

        if target_group_arn is not None:
            if len(container.PortMappings) < 1:
                raise ValueError(
                    "Container '%s' connects to an ELB but does not specify port_mappings or container_port"
                    % c["name"]
                )
            lb_mappings.append(
                LoadBalancer(
                    ContainerName=container.Name,
                    # TODO: Ugly hack, do better.
                    ContainerPort=container.PortMappings[0].ContainerPort,
                    TargetGroupArn=target_group_arn,
                )
            )

    task_def(containers, efs_volumes, exec_role)
    service(
        user_data.service_tags,
        listener_rules,
        lb_mappings,
        user_data.placement_strategies,
    )

    schedule = user_data.schedule
    if len(schedule) > 0:
        lambda_execution_role()
        scheduling_lambda()
        for p in schedule:
            rule = scheduling_rule(p)
            lambda_invoke_permission(rule)

    return TEMPLATE.to_json()
