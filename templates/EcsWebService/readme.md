# EcsWebService

Creates an ECS service along with it's related load-balancer resources like
listener rules and a target group.

## Features

- EFS integration (`sceptre_user_data.efs_volumes`)
- Service scheduling (`sceptre_user_data.schedule`)
- Image building through CodeBuild (`sceptre_user_data.containers.*.image_build`)
- ELB listener rules (`sceptre_user_data.containers.*.rules`)

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

- `auto_stop` ([AutoStopModel](#AutoStopModel)) - Configuration for automatically stopping the service after a period of innactivity.
  - **Default:** This feature is disabled by default.

- `containers` (List of [ContainerModel](#ContainerModel)) - **required** - Defines the containers for this service.

- `cpu` (string) - The number of cpu units used by the task.
  - If you are using the `FARGATE` launch type, this value is
            required. See
            [AWS::ECS::TaskDefinition](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-ecs-taskdefinition.html#cfn-ecs-taskdefinition-cpu)
            for details.

- `efs_volumes` (List of [EfsVolumeModel](#EfsVolumeModel)) - Set of EFS volumes to make available to containers within this service.
  - To make an EFS volume available to a container you must define it in the `efs_volumes` setting and define an entry in the `mount_points` setting within the container object.

- `host_volumes` (List of [HostVolumeModel](#HostVolumeModel)) - Set of directories on the host server to make available to containers within this service.
  - **Important:** You almost always will want to use `efs_volumes` instead.
  - To make an EFS volume available to a container you must define it in the
               `host_volumes` setting and define an entry in the `mount_points`
               setting within the container object.

- `launch_type` (string)
  - **Allowed Values:** `EC2`, `EXTERNAL`, `FARGATE`

- `memory` (string) - The amount (in MiB) of memory used by the task.
  - If you are using the `FARGATE` launch type, this value is
            required. See
            [AWS::ECS::TaskDefinition](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-ecs-taskdefinition.html#cfn-ecs-taskdefinition-memory)
            for details.

- `network_mode` (string) - The Docker networking mode to use for the containers in the task.
  - See [AWS::ECS::TaskDefinition](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-ecs-taskdefinition.html#cfn-ecs-taskdefinition-networkmode) for details.

- `placement_strategies` (List of [PlacementStrategyModel](#PlacementStrategyModel)) - Defines the set of placement strategies for service tasks.

- `requires_compatibilities` (List of string) - The task launch types the task definition was validated against.
  - **See Also:** [TaskDefinition$compatibilities](https://docs.aws.amazon.com/AmazonECS/latest/APIReference/API_TaskDefinition.html#ECS-Type-TaskDefinition-compatibilities)

- `schedule` (List of [ScheduleModel](#ScheduleModel)) - Specifies a schedule for modifying the DesiredCount of the service.

- `security_group` ([SecurityGroupModel](#SecurityGroupModel)) - Defines a security group of which all service containers will be members.
  - This property only applies when `network_mode` is `awsvpc`.

- `security_group_ids` (List of string) - List of security group IDs of which all service containers will be members.
  - This property only applies when `network_mode` is `awsvpc`.

- `service_tags` (Dict[string:string]) - A dict of tags to apply to the ECS service.

- `subnet_ids` (List of string) - The IDs of the subnets associated with the task or service.
  - This property only applies when `network_mode` is `awsvpc`.



### AutoStopModel

**WARNING:** This feature is in alpha state and is subject to change without notice.

- `enabled` (boolean) - When `True` the service will be stopped after a period of innactivity.
  - **Default:** `False`

- `idle_check_schedule` (string) - An EventBridge schedule expression for when the service should be checked for idleness.
  - **Default:** `rate(1 hour)`
  - Do not set this too frequently since the idle check is a Lambda invocation and has a small cost.
  - See [Schedule Expressions for Rules](https://docs.aws.amazon.com/AmazonCloudWatch/latest/events/ScheduledEvents.html) for details.

- `idle_minutes` (integer) - Number of minutes without a request before the service is considered idle and can be stopped.
  - **Default:** `240`

- `waiter_css` (string) - CSS to apply to the 'please wait' page.
  - **Default:** `/* */`

- `waiter_explanation` (string) - The explanatory text that appears on the 'please wait' page.
  - **Default:** `This service has been shut down due to inactivity. It is now being
           restarted and will be available again shortly.`

- `waiter_heading` (string) - The heading that appears at the top of the 'please wait' page.
  - **Default:** `Please wait while the service starts...`

- `waiter_page_title` (string) - Title for the 'please wait' page.
  - **Default:** If no value is provided, the name of the stack will be used.

- `waiter_refresh_seconds` (integer) - Number of seconds between refreshes of the 'please wait' page.
  - **Default:** `10`



### ScheduleModel

- `cron` (string) - **required** - Cron expression for when this schedule fires. Only cron expressions are
                       supported and the `cron()` clause is implied. So values
                       should be specified like `0 0 * * ? *` instead of `cron(0
                       12 * * ? *)`.
  - AWS requires that all cron expressions be in UTC. It is not possible at this
               time to specify a local timezone. You will therefore need to
               adjust your cron expressions appropriately.
  - **See Also:** [Schedule Expressions for Rules](https://docs.aws.amazon.com/AmazonCloudWatch/latest/events/ScheduledEvents.html#CronExpressions)

- `description` (string) - Description of the schedule

- `desired_count` (integer) - **required** - Desired number of tasks to set for the service at the specified time.



### PlacementStrategyModel

**See:** [AWS::ECS::Service PlacementStrategy](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-ecs-service-placementstrategy.html)
for more information.

- `field` (string) - **required** - The field to apply the placement strategy against

- `type` (string) - **required** - The type of placement strategy



### HostVolumeModel

- `name` (string) - **required** - This is the name which will be referred to by `source_volume` values defined in the
                       `mount_points` settings of a container.

- `source_path` (string)
  - **Default:** `The path on the host server that's presented to the container.`



### EfsVolumeModel

- `fs_id` (string) - **required** - The ID of the EFS volume

- `name` (string) - **required** - This is the name which will be referred to by `source_volume` values defined in the
                       `mount_points` settings of a container.

- `root_directory` (string) - The directory within the EFS volume which will mounted by containers
  - **Default:** By default the root directory of the volume will be used.



### ContainerModel

- `command` (List of string) - Maps to the COMMAND parameter of [docker run](https://docs.docker.com/engine/reference/run/#security-configuration).

- `container_extra_props` (Dict) - Additional options to include in the ContainerDefinition
  - **See Also:** [AWS::ECS::TaskDefinition ContainerDefinition](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-ecs-taskdefinition-containerdefinitions.html)

- `container_health_check` (Dict) - Container health check as defined in [AWS::ECS::TaskDefinition HealthCheck](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-ecs-taskdefinition-healthcheck.html)

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

- `container_memory_reservation` (integer) - The soft limit (in MiB) of memory to reserve for the container.
  - If you specify both `container_memory` and `container_memory_reservation`,
               `container_memory` must be greater than
               `container_memory_reservation`. If you specify
               `container_memory_reservation`, then that value is subtracted
               from the available memory resources for the container instance on
               which the container is placed. Otherwise, the value of
               `container_memory` is used.

- `container_port` (integer) - The port exposed by the container
  - One of `container_port` or `port_mappings` must be defined for any container connecting to an ELB.

- `depends_on` (List of Dict) - List of container dependencies as defined in [AWS::ECS::TaskDefinition ContainerDependency](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-ecs-taskdefinition-containerdependency.html)

- `env_vars` (Dict[string:string]) - Environment variables passed to the container.

- `health_check` ([HealthCheckModel](#HealthCheckModel)) - Defines the health check for the target group. If `rules` is not specified
                       for the container, this setting has no effect.

- `image` (string) - The URI of the container image.
  - **Requirement:** One of `image` or `image_build` must be defined
  - [AWS::ECS::TaskDefinition ContainerDefinition](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-ecs-taskdefinition-containerdefinitions.html#cfn-ecs-taskdefinition-containerdefinition-image)

- `image_build` ([ImageBuildModel](#ImageBuildModel)) - Settings for building the container image.
  - **Requirement:** One of `image` or `image_build` must be defined

- `links` (List of string) - List of container `names` to which to link this container. The `links`
                       parameter allows containers to communicate with each
                       other without the need for port mappings.
  - **See Also:** [AWS::ECS::TaskDefinition ContainerDefinition](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-ecs-taskdefinition-containerdefinitions.html#cfn-ecs-taskdefinition-containerdefinition-links)

- `linux_parameters` (Dict) - Linux-specific options that are applied to the container
  - **See Also:** [AWS::ECS::TaskDefinition LinuxParameters](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-ecs-taskdefinition-linuxparameters.html#cfn-ecs-taskdefinition-linuxparameters-sharedmemorysize)

- `mount_points` (List of [MountPointModel](#MountPointModel)) - Maps volumes defined in `sceptre_user_data.efs_volumes` to mount points within the container.

- `name` (string) - The name of the container
  - **Default:** `main`

- `port_mappings` (List of [PortMappingModel](#PortMappingModel)) - List of port-mappings to assign to the container.
  - **Requirement:** One of `container_port` or `port_mappings` must be defined for any container connecting to an ELB.

- `protocol` (string) - The back-end protocol used by the load-balancer to communicate with the container
  - **Default:** `HTTP`

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

- `target_group` ([TargetGroupModel](#TargetGroupModel)) - Extended options for the target group. If `rules` is not specified for the
                       container, this setting has no effect.
  - **Default:** `{'attributes': {}}`

- `target_group_arn` (string) - ARN of the ELB target group to for the container. If this option is specified
                       instead of `rules` then no target group will be created.
                       Instead, the container will be assigned to an
                       externally-defined target group. This is normally used to
                       assign a container to the default target group of an
                       ELB.



#### TargetGroupModel

- `attributes` (Dict[string:string]) - Sets target group attributes
  - **Default:** The following attributes are defined by default:
    * `'stickiness.enabled' = 'true'`
    * `'stickiness.type' = 'lb_cookie'`
  - **See Also:** [AWS::ElasticLoadBalancingV2::TargetGroup TargetGroupAttribute](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-elasticloadbalancingv2-targetgroup-targetgroupattribute.html)



#### RuleModel

- `container_port` (integer) - The container port associated with this rule's traffic.
  - This field is only required if you need to send traffic to
               multiple ports within the container. You must include this port
               in the container's `port_mappings` key.

- `health_check` ([HealthCheckModel](#HealthCheckModel)) - Health check for this rule. This overrides the `health_check` specified on the container.

- `host` (string) - Pattern to match against the request's host header. Wildcards `?` and `*` are supported.
  - For this setting to work properly, the ELB will need to be set up to for multiple hostnames.
  - **See Also:** [AWS::ElasticLoadBalancingV2::ListenerRule HostHeaderConfig](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-elasticloadbalancingv2-listenerrule-hostheaderconfig.html)

- `listener_arn` (string) - ARN of the listener for this rule. Overrides the ListenerArn parameter.

- `path` (string) - **required** - The context path for the listener rule. The path should start with a `/`. Two
                       listener rules will be created, one matching `path` and
                       one matching `path + '/*'`.

- `priority` (integer) - The priority value for the listener rule. If undefined, a hash-based value will be generated.

- `protocol` (string) - The back-end protocol used by the load-balancer to
                       communicate with the container. This overrides the
                       `protocol` specified on the container.

- `target_group` ([TargetGroupModel](#TargetGroupModel)) - Extended options for the target group for this rule. This
                       overrides the `target_group` specified on the container.

- `target_group_arn` (string) - ARN of an existing target group on the ELB. If this value
                       is specified then a target group will not be created for
                       this rule.



##### HealthCheckModel

- `healthy_threshold_count` (integer) - The number of consecutive health checks successes required before considering
                       an unhealthy target healthy.

- `http_code` (string) - HTTP status code(s) the health check will consider "healthy." You can specify
                       values between 200 and 499, and the default value is 200.
                       You can specify multiple values (for example, "200,202")
                       or a range of values (for example, "200-299").
  - **Default:** `200-399`

- `interval_seconds` (integer) - The approximate amount of time between health checks of an individual target.
  - **Default:** `60`

- `path` (string) - Path the target group health check will request

- `timeout_seconds` (integer) - The amount of time during which no response from a target means a failed health check.
  - **Default:** `30`

- `unhealthy_threshold_count` (integer) - The number of consecutive health check failures required before considering a
                       target unhealthy.
  - **Default:** `5`



#### MountPointModel

- `container_path` (string) - **required** - The mount point for the volume within the container

- `read_only` (boolean) - If true, the volume will not be writable to the container.
  - **Default:** `False`

- `source_volume` (string) - **required** - The `name` value specified for the volume in `sceptre_user_data.efs_volumes`.



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

- `name` (string) - **required** - The name or key of the environment variable.

- `type` (string) - The type of environment variable.
  - **Default:** `PLAINTEXT`
  - **Allowed Values:** `PLAINTEXT`, `PARAMETER_STORE`, `SECRETS_MANAGER`

- `value` (string) - **required** - The value of the environment variable.



### SecurityGroupModel

- `allow` (List of [SecurityGroupAllowModel](#SecurityGroupAllowModel) or List of [SecurityGroupAllowModel](#SecurityGroupAllowModel)) - Rules for allowed inbound traffic.

- `egress` (List of Dict[string:string]) - The outbound rules associated with the security group.
  - **Default:** Allow all outbound traffic.

- `tags` (Dict[string:string]) - Tags applied to security group.



#### SecurityGroupAllowModel

- `cidr` (string or List of string) - The IPv4 address range(s), in CIDR format. May be specified as a single string or a list of strings.
  - You must specify one of `cidr` or `sg_id` but not both.

- `description` (string) - **required** - Description of the rule.

- `from_port` (integer) - The start of port range for the TCP and UDP protocols. A value of `-1` indicates all ports.
  - You must specify either `port` or `from_port` and `to_port` but not both.

- `port` (string or integer) - Port or port range for the TCP and UDP protocols.
  - You must specify either `port` or `from_port` and `to_port` but not both.
  - A single number will specify a single port.
  - A range of ports is specified with a hyphen (eg. `100-199`)
  - To allow any port specify `any`.

- `protocol` (string) - The IP protocol name.
  - **Default:** `tcp`

- `sg_id` (string) - The ID of a security group whose members are allowed.
  - You must specify one of `cidr` or `sg_id` but not both.

- `sg_owner` (string) - The AWS account ID that owns the security group specified in `sg_id`. This value is required if the SG is in another account.

- `to_port` (integer) - The start of port range for the TCP and UDP protocols. A value of `-1` indicates all ports.
  - You must specify either `port` or `from_port` and `to_port` but not both.

