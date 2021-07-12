# EcsWebService.py - ECS Service With Load-Balancer Integration

  * [Parameters](#parameters)
  * [sceptre_user_data](#sceptre-user-data)
    + [container objects](#container-objects)
      - [health check object](#health-check-object)
      - [mount point objects](#mount-point-objects)
      - [port mapping objects](#port-mapping-objects)
      - [rule objects](#rule-objects)
      - [schedule objects](#schedule-objects)
      - [target group object](#target-group-object)
    + [efs volume objects](#efs-volume-objects)
    + [placement strategy objects](#placement-strategy-objects)


## Parameters

* `VpcId` (string) - *Required* - The ID of the VPC of the ECS cluster
* `ListenerArn` (string) - *Required* - The ARN of the ELB listener which will be used by this service
* `ClusterArn` (string) - *Required* - The ARN or name of the ECS cluster
* `DesiredCount` (number) - The desired number of instances of this service
  * **Default:** `1`
* `MaximumPercent` (number) - The maximum percent of `DesiredCount` allowed to be running during updates.
  * **Default:** `200`
  * **See also:** [AWS::ECS::Service DeploymentConfiguration](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-ecs-service-deploymentconfiguration.html#cfn-ecs-service-deploymentconfiguration-maximumpercent)
* `MinimumHealthyPercent` (number) - The minimum number of running instances of this service to keep running during an
  update.
  * **Default:** `100`
  * **See also:** [AWS::ECS::Service DeploymentConfiguration](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-ecs-service-deploymentconfiguration.html#cfn-ecs-service-deploymentconfiguration-minimumhealthypercent)
  


## sceptre_user_data

* `containers` (list of [container objects](#container-objects)) - *Required* - Defines the containers for this service.

* `efs_volumes` (list of [efs volume objects](#efs-volume-objects)) - Set of EFS volumes to make available to
  containers within this service.
  * **Note:** To make an EFS volume available to a container you must define it in the `efs_volumes` setting and define
    an entry in the `mount_points` setting within the container object.
  
* `placement_strategies` (list of [placement strategy objects](#placement-strategy-objects)) - Defines the set of
  placement strategies for service tasks.
  * **Default:** `[{'field': 'memory', 'type': 'binpack'}]`

* `schedule` (list of [schedule objects](#schedule-objects)) - Specifies a schedule for modifying the DesiredCount of
  the service.



### container objects

* `image` (string) - *Required* - The image used to start a container.
  * **See Also:** [AWS::ECS::TaskDefinition ContainerDefinition](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-ecs-taskdefinition-containerdefinitions.html#cfn-ecs-taskdefinition-containerdefinition-image)
  
* `container_port` (number) - The port exposed by the container
  * **Requirement:** One of `container_port` or `port_mappings` must be defined for any container connecting to an ELB.
    
* `port_mappings` (list of [port mapping objects](#port-mapping-objects)) - List of port-mappings to assign to the
  container.
  * **Requirement:** One of `container_port` or `port_mappings` must be defined for any container connecting to an ELB.
   
* `container_memory` (number) - The amount (in MiB) of memory to present to the container. If your container attempts to
  exceed the memory specified here, the container is killed.
  * **Default:** `512`
  * **Note:** If you specify both `container_memory` and `container_memory_reservation`, `container_memory` must be 
    greater than `container_memory_reservation`. If you specify `container_memory_reservation`, then that value is 
    subtracted from the available memory resources for the container instance on which the container is placed. 
    Otherwise, the value of `container_memory` is used.

* `container_memory_reservation` (number) - The soft limit (in MiB) of memory to reserve for the container.
  * **Default:** Equal to `container_memory`
  * **Note:** If you specify both `container_memory` and `container_memory_reservation`, `container_memory` must be 
    greater than `container_memory_reservation`. If you specify `container_memory_reservation`, then that value is 
    subtracted from the available memory resources for the container instance on which the container is placed. 
    Otherwise, the value of `container_memory` is used.

* `env_vars` (string:string dictionary) - Environment variables passed to the container.
  
* `health_check` ([health check object](#health-check-object)) - Defines the health check for the target group. If 
  `rules` is not specified for the container, this setting has no effect.
  
* `links` (list of strings) - List of container `names` to which to link this container. The `links` parameter allows 
  containers to communicate with each other without the need for port mappings.
  * **See Also:** [AWS::ECS::TaskDefinition ContainerDefinition](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-ecs-taskdefinition-containerdefinitions.html#cfn-ecs-taskdefinition-containerdefinition-links)
  
* `mount_points` (list of [mount point objects](#mount-point-objects)) - Maps volumes defined in 
  `sceptre_user_data.efs_volumes` to mount points within the container.
  
* `name` (string) - The name of the container
  * **Default:** `main`
 
* `protocol` (string) - The back-end protocol used by the load-balancer to communicate with the container
  * **Default:** `HTTP`
  * **Allowed Values:** `HTTP`, `HTTPS`
    
* `rules` (list of [rules objects](#rule-objects)) - If specified, the stack will create an ELB target group and add
  the specified rules to the listener to route traffic.
 
* `secrets` (string:string dictionary) - Secrets passed as environment variables to the container. The key will specify
  the variable being set. The value specifies where ECS should read the value from.
  * **Note:** The supported values are either the full ARN of the AWS Secrets Manager secret or the full ARN of the 
    parameter in the SSM Parameter Store. If the SSM Parameter Store parameter exists in the same Region as the task you
    are launching, then you can use either the full ARN or name of the parameter. If the parameter exists in a different
    Region, then the full ARN must be specified.
    
* `target_group` ([target group object](#target-group-object)) - Extended options for the target group. If `rules` is 
  not specified for the container, this setting has no effect.
  
* `target_group_arn` (string) - ARN of the ELB target group to for the container. If this option is specified instead of
  `rules` then no target group will be created. Instead, the container will be assigned to an externally-defined target
  group. This is normally used to assign a container to the default target group of an ELB. 



#### health check object

* `path` (string) - Path the target group health check will request
  * **Default:** If unspecified, the `path` value of the first [rule](#rule-objects) will be used.



#### mount point objects

* `container_path` (string) - *Required* - The mount point for the volume within the container

* `source_volume` (string) - *Required* - The `name` value specified for the volume in `sceptre_user_data.efs_volumes`.

* `read_only` (boolean) - If true, the volume will not be writable to the container.
  * **Default:** `false`



#### port mapping objects

* `container_port` (number) - *required* - The port exposed by the container
  * **Note:** You may specify more than one port mapping object per container, but the target group will always route
    its traffic to the `container_port` of the first port mapping.



#### rule objects

* `path` (string) - *Required* - The context path for the listener rule. The path should start with a `/`. Two listener
  rules will be created, one matching `path` and one matching `path + '/*'`.

* `priority` (number) - The priority value for the listener rule. If undefined, a hash-based value will be generated.



#### schedule objects

* `cron` (string) - *Required* - Cron expression for when this schedule fires. Only cron expressions are supported and 
  the `cron()` clause is implied. So values should be specified like `0 0 * * ? *` instead of `cron(0 12 * * ? *)`.
  * **Note:** AWS requires that all cron expressions be in UTC. It is not possible at this time to specify a local
    timezone. You will therefore need to adjust your cron expressions appropriately.
  * **See Also:** [Schedule Expressions for Rules](https://docs.aws.amazon.com/AmazonCloudWatch/latest/events/ScheduledEvents.html#CronExpressions)
  
* `desired_count` (number) - *Required* - Desired number of tasks to set for the service at the specified time.

* `description` (string) - Description of the schedule



#### target group object

* `attributes` - (string:string dictionary) - Sets target group attributes
  * **Defaults:** The following attributes are defined by default:
    * `'stickiness.enabled' = 'true'`
    * `'stickiness.type' = 'lb_cookie'`
  * **See Also:** [AWS::ElasticLoadBalancingV2::TargetGroup TargetGroupAttribute](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-elasticloadbalancingv2-targetgroup-targetgroupattribute.html)



### efs volume objects

* `name` (string) - *Required* - This is the name which will be referred to by `source_volume` values defined in the
  `mount_points` settings of a container.
  
* `fs_id` (string) - *Required* - The ID of the EFS volume

* `root_directory` (string) - The directory within the EFS volume which will mounted by containers
  * **Default:** By default the root directory of the volume will be used.
    


### placement strategy objects

**See:** [AWS::ECS::Service PlacementStrategy](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-ecs-service-placementstrategy.html)
  for more information.

* `field` (string) - *Required* - The field to apply the placement strategy against
* `type` (string) - *Required* - The type of placement strategy
