## Parameters

- `ClusterArn` (String) - **required** - The ARN or name of the ECS cluster

- `DesiredCount` (Number) - The desired number of instances of this service
  - **Default:** `1`

- `ListenerArn` (String) - **required** - The ARN of the ELB listener which will be used by this service

- `MaximumPercent` (Number) - The maximum percent of `DesiredCount` allowed to be running during updates.
  - **Default:** `200`

- `MinimumHealthyPercent` (Number) - The minimum number of running instances of this service to keep running during an update.
  - **Default:** `100`

- `VpcId` (String) - **required** - The ID of the VPC of the ECS cluster



## sceptre_user_data

- `service_tags` (Dict[string:string])

- `containers` (List of [ContainerModel](#ContainerModel)) - **required** - Defines the containers for this service.

- `efs_volumes` (List of [EfsVolumeModel](#EfsVolumeModel)) - Set of EFS volumes to make available to containers within this service.
  - To make an EFS volume available to a container you must define it in the `efs_volumes` setting and define an entry in the `mount_points` setting within the container object.

- `placement_strategies` (List of [PlacementStrategyModel](#PlacementStrategyModel)) - Defines the set of placement strategies for service tasks.
  - **Default:** `[{'field': 'memory', 'type': 'binpack'}]`

- `schedule` (List of [ScheduleModel](#ScheduleModel)) - Specifies a schedule for modifying the DesiredCount of the service.



### ScheduleModel

- `cron` (string) - **required** - Cron expression for when this schedule fires. Only cron expressions are
                       supported and the `cron()` clause is implied. So values
                       should be specified like `0 0 * * ? *` instead of `cron(0
                       12 * * ? *)`.
  - AWS requires that all cron expressions be in UTC. It is not possible at this
               time to specify a local timezone. You will therefore need to
               adjust your cron expressions appropriately.
  - **See Also:** [Schedule Expressions for Rules](https://docs.aws.amazon.com/AmazonCloudWatch/latest/events/ScheduledEvents.html#CronExpressions)

- `desired_count` (integer) - **required** - Desired number of tasks to set for the service at the specified time.

- `description` (string) - Description of the schedule



### PlacementStrategyModel

**See:** [AWS::ECS::Service PlacementStrategy](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-ecs-service-placementstrategy.html)
for more information.

- `field` (string) - **required** - The field to apply the placement strategy against

- `type` (string) - **required** - The type of placement strategy



### EfsVolumeModel

- `name` (string) - **required** - This is the name which will be referred to by `source_volume` values defined in the
                       `mount_points` settings of a container.

- `fs_id` (string) - **required** - The ID of the EFS volume

- `root_directory` (string) - The directory within the EFS volume which will mounted by containers
  - **Default:** By default the root directory of the volume will be used.



### ContainerModel

- `image` (string) - The URI of the container image.
  - **Requirement:** One of `image` or `image_build` must be defined
  - [AWS::ECS::TaskDefinition ContainerDefinition](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-ecs-taskdefinition-containerdefinitions.html#cfn-ecs-taskdefinition-containerdefinition-image)

- `image_build` ([ImageBuildModel](#ImageBuildModel)) - Settings for building the container image.
  - **Requirement:** One of `image` or `image_build` must be defined

- `container_port` (integer) - The port exposed by the container
  - One of `container_port` or `port_mappings` must be defined for any container connecting to an ELB.

- `port_mappings` (List of [PortMappingModel](#PortMappingModel)) - List of port-mappings to assign to the container.
  - **Requirement:** One of `container_port` or `port_mappings` must be defined for any container connecting to an ELB.

- `container_memory_reservation` (integer) - The soft limit (in MiB) of memory to reserve for the container.
  - If you specify both `container_memory` and `container_memory_reservation`,
               `container_memory` must be greater than
               `container_memory_reservation`. If you specify
               `container_memory_reservation`, then that value is subtracted
               from the available memory resources for the container instance on
               which the container is placed. Otherwise, the value of
               `container_memory` is used.

- `env_vars` (Dict[string:string]) - Environment variables passed to the container.

- `health_check` ([HealthCheckModel](#HealthCheckModel)) - Defines the health check for the target group. If `rules` is not specified
                       for the container, this setting has no effect.

- `links` (List of string) - List of container `names` to which to link this container. The `links`
                       parameter allows containers to communicate with each
                       other without the need for port mappings.
  - **See Also:** [AWS::ECS::TaskDefinition ContainerDefinition](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-ecs-taskdefinition-containerdefinitions.html#cfn-ecs-taskdefinition-containerdefinition-links)

- `mount_points` (List of [MountPointModel](#MountPointModel)) - Maps volumes defined in `sceptre_user_data.efs_volumes` to mount points within the container.

- `rules` (List of [RuleModel](#RuleModel)) - If specified, the stack will create an ELB target group and add the specified
                       rules to the listener to route traffic.

- `secrets` (Dict[string:string]) - Secrets passed as environment variables to the container. The key will
                       specify the variable being set. The value specifies where
                       ECS should read the value from.
  - The supported values are either the full ARN of the AWS Secrets Manager
                  secret or the full ARN of the parameter in the SSM Parameter
                  Store. If the SSM Parameter Store parameter exists in the same
                  Region as the task you are launching, then you can use either
                  the full ARN or name of the parameter. If the parameter exists
                  in a different Region, then the full ARN must be specified.

- `target_group_arn` (string) - ARN of the ELB target group to for the container. If this option is specified
                       instead of `rules` then no target group will be created.
                       Instead, the container will be assigned to an
                       externally-defined target group. This is normally used to
                       assign a container to the default target group of an
                       ELB.

- `linux_parameters` (Dict) - Linux-specific options that are applied to the container
  - **See Also:** [AWS::ECS::TaskDefinition LinuxParameters](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-ecs-taskdefinition-linuxparameters.html#cfn-ecs-taskdefinition-linuxparameters-sharedmemorysize)

- `container_extra_props` (Dict) - Additional options to include in the ContainerDefinition
  - **See Also:** [AWS::ECS::TaskDefinition ContainerDefinition](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-ecs-taskdefinition-containerdefinitions.html)

- `container_memory` (integer) - The amount (in MiB) of memory to present to the container. If your container
                       attempts to exceed the memory specified here, the
                       container is killed.
  - **Default:** `512`
  - If you specify both `container_memory` and `container_memory_reservation`,
               `container_memory` must be greater than
               `container_memory_reservation`. If you specify
               `container_memory_reservation`, then that value is subtracted
               from the available memory resources for the container instance on
               which the container is placed. Otherwise, the value of
               `container_memory` is used.

- `name` (string) - The name of the container
  - **Default:** `main`

- `protocol` (string) - The back-end protocol used by the load-balancer to communicate with the container
  - **Default:** `HTTP`

- `target_group` ([TargetGroupModel](#TargetGroupModel)) - Extended options for the target group. If `rules` is not specified for the
                       container, this setting has no effect.
  - **Default:** `{'attributes': {}}`



#### TargetGroupModel

- `attributes` (Dict[string:string]) - Sets target group attributes
  - **Default:** The following attributes are defined by default:
    * `'stickiness.enabled' = 'true'`
    * `'stickiness.type' = 'lb_cookie'`
  - **See Also:** [AWS::ElasticLoadBalancingV2::TargetGroup TargetGroupAttribute](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-elasticloadbalancingv2-targetgroup-targetgroupattribute.html)



#### RuleModel

- `path` (string) - **required** - The context path for the listener rule. The path should start with a `/`. Two
                       listener rules will be created, one matching `path` and
                       one matching `path + '/*'`.

- `host` (string) - Pattern to match against the request's host header. Wildcards `?` and `*` are supported.
  - For this setting to work properly, the ELB will need to be set up to for multiple hostnames.
  - **See Also:** [AWS::ElasticLoadBalancingV2::ListenerRule HostHeaderConfig](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-elasticloadbalancingv2-listenerrule-hostheaderconfig.html)

- `priority` (integer) - The priority value for the listener rule. If undefined, a hash-based value will be generated.



#### MountPointModel

- `container_path` (string) - **required** - The mount point for the volume within the container

- `source_volume` (string) - **required** - The `name` value specified for the volume in `sceptre_user_data.efs_volumes`.

- `read_only` (boolean) - If true, the volume will not be writable to the container.
  - **Default:** `False`



#### HealthCheckModel

- `path` (string) - Path the target group health check will request

- `healthy_threshold_count` (integer) - The number of consecutive health checks successes required before considering
                       an unhealthy target healthy.

- `interval_seconds` (integer) - The approximate amount of time between health checks of an individual target.
  - **Default:** `60`

- `timeout_seconds` (integer) - The amount of time during which no response from a target means a failed health check.
  - **Default:** `30`

- `unhealthy_threshold_count` (integer) - The number of consecutive health check failures required before considering a
                       target unhealthy.
  - **Default:** `5`

- `http_code` (string) - HTTP status code(s) the health check will consider "healthy." You can specify
                       values between 200 and 499, and the default value is 200.
                       You can specify multiple values (for example, "200,202")
                       or a range of values (for example, "200-299").
  - **Default:** `200-399`



#### PortMappingModel

- `container_port` (integer) - **required** - The port exposed by the container
  - You may specify more than one port mapping object per container, but the
               target group will always route its traffic to the
               `container_port` of the first port mapping.



#### ImageBuildModel

- `codebuild_project_name` (string) - **required** - Name of the CodeBuild project which builds the image.

- `ecr_repo_name` (string) - **required** - Name of the ECR repo into which the build image will be pushed.

- `env_vars` (List of [EnvironmentVariableModel](#EnvironmentVariableModel)) - Environment variable overrides for the build.



##### EnvironmentVariableModel

- `name` (string) - **required**

- `value` (string) - **required**

- `type` (string)
  - **Default:** `PLAINTEXT`
  - **Allowed Values:** `PLAINTEXT`, `PARAMETER_STORE`, `SECRETS_MANAGER`

