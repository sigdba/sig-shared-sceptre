from typing import Dict, List, Optional
from pydantic import Field, validator, root_validator
from pydantic import BaseModel as PydanticBaseModel

from util import *

# Create a custom BaseModel which forbids extra parameters. This ensures that
# when a user misspells a key they will get an error instead of some undefined
# behavior.
class BaseModel(PydanticBaseModel):
    class Config:
        extra = "forbid"


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


class HostVolumeModel(BaseModel):
    name: str = Field(
        description="""This is the name which will be referred to by `source_volume` values defined in the
                       `mount_points` settings of a container."""
    )
    source_path: str = Field(
        """The path on the host server that's presented to the container."""
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

    @classmethod
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

    @classmethod
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

    @classmethod
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
    host_volumes: List[HostVolumeModel] = Field(
        [],
        description="Set of directories on the host server to make available to containers within this service.",
        notes=[
            """**Important:** You almost always will want to use `efs_volumes` instead.""",
            """To make an EFS volume available to a container you must define it in the
               `host_volumes` setting and define an entry in the `mount_points`
               setting within the container object.""",
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