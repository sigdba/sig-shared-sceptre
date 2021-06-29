# EcsCluster.py - ECS Cluster With Optional Auto-Scaling Features

**See Also:**
* [Example Configuration](../examples/EcsCluster.yaml)
* [Changing instance types with auto-scaling enabled](EcsCluster_NodeTypeChangeWithAutoScaling.md)

## Parameters

* `EnvName` (string) - *Required* - The name of the ECS cluster
* `VpcId` (string) - *Required* - The ID of the VPC where the ECS cluster will be created.
* `Subnets` (list of strings) - *Required* - IDs of the subnets where container instances will be created. These should
  be "private" subnets behind a NAT.

## sceptre_user_data

* `node_security_groups` (list of strings) - *required* - List of security group IDs which will be assigned to all
  container instances.
  
* `ssm_key_admins` (list of strings) - *required* - List of ARNs of IAM users/roles which will be granted permission to
  manage the encryption key.
  * **Default:** `['arn:aws:iam::${AWS::AccountId}:root']`
  * **Note:** This setting is retained for backward compatibility, but it is now recommended to use AWS Secrets Manager
    rather than the SSM parameter store.
    
* `ingress_cidrs` (list of strings) - *required* - List of CIDRs which will be allowed to communicate with the container
  instances. This must include at least the load-balancer subnets which will be associated with services on this 
  cluster.
  
* `auto_scaling_enabled` (boolean) - When true, auto-scaling features will be enabled on the cluster based on ECS
  capacity providers.
  * **Default:** `false`
  * **Note:** Once a capacity provider has been assigned to an ECS service it can be changed but it cannot be removed.
    Therefore, once auto-scaling has been enabled on a cluster, it will be necessary to remove all services before
    auto-scaling can be disabled again.
    
* `force_default_cps` (boolean) - When true, changes to the `scaling_groups` will trigger an update of all services on
  the cluster, forcing them to use the new default capacity provider(s). This setting has no effect if 
  `auto_scaling_enabled == false`.
  * **Default:** `false`
  * **Note:** This setting defaults to false, but if you're using auto-scaling then you probably want to set it to true
    unless you're manually managing the capacity provider strategies for each service.
    
* `scaling_groups` (list of [scaling_group objects](#scaling_group-objects)) - *required* - One or more `scaling_group` objects defining the EC2
  Auto-Scaling Group(s) which will provide container instances for the cluster.
  
### scaling_group Objects

* `name` (string) - *required* - The name to assign the scaling group.
  
* `key_name` (string) - *required* - The name of the SSH key to assign when creating container instances.
  
* `node_type` (string) - *required* - The EC2 instance type of the container instances in this scaling group.

* `max_size` (number) - *required* - The maximum number of container instances allowed in this scaling group.

* `desired_size` (number) - *required* - The desired number of container instances in this scaling group.
  * **Note:** If `auto_scaling_enabled` is true, then ECS may modify the desired size of the scaling group to match 
    demand.
    
* `in_default_cps` (boolean) - When true, this scaling group will participate in the default capacity provider strategy
  for the cluster. This option has no effect if `auto_scaling_enabled` is false.
  * **Default:** `true`
  * **See also:** [Changing instance types with auto-scaling enabled](EcsCluster_NodeTypeChangeWithAutoScaling.md)
    
* `weight` (number) - Sets the weight of the scaling group within the default capacity provider strategy. This option 
  has no effect if `auto_scaling_enabled` is false. 
  * **Default:** `1`
  * **See also:** [AWS::ECS::Service CapacityProviderStrategyItem](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-ecs-service-capacityproviderstrategyitem.html#cfn-ecs-service-capacityproviderstrategyitem-weight)