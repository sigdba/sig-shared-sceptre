# EcsCluster
Creates an EC2-backed cluster in ECS with optional auto-scaling.

## Parameters

- `AmiId` (AWS::SSM::Parameter::Value<AWS::EC2::Image::Id>) - AMI ID for EC2 cluster nodes
  - **Default:** `/aws/service/ecs/optimized-ami/amazon-linux-2023/recommended/image_id`

- `EnvName` (String) - **required** - The name of the ECS cluster.

- `VpcId` (String) - **required** - The ID of the VPC where the ECS cluster will be created.



## sceptre_user_data

- `asg_tags` (Dict[string:string]) - Tags to apply to all ASG EC2 instances.

- `auto_scaling_enabled` (boolean) - When true, auto-scaling features will be enabled on the cluster based on ECS capacity providers.
  - **Default:** `True`
  - **Warning:** Once a capacity provider has been assigned to an ECS
               service it can be changed but it cannot be removed. Therefore,
               once auto-scaling has been enabled on a cluster, it will be
               necessary to remove all services before auto-scaling can be
               disabled again.

- `cluster_tags` (Dict[string:string]) - Tags to apply to the cluster.

- `container_insights_enabled` (boolean) - When true, Container Insights will be enabled.
  - **Default:** `False`
  - Container Insights can be surprisingly expensive. Be sure to
               review the [CloudWatch Pricing page](https://aws.amazon.com/cloudwatch/pricing/)
               and note the pricing example for Container Insights.

- `force_default_cps` (boolean) - When true, changes to the `scaling_groups` will trigger
                       an update of all services on the cluster, forcing them to
                       use the new default capacity provider(s). This setting
                       has no effect if `auto_scaling_enabled == false`. 
  - **Default:** `False`
  - This setting defaults to false, but if you're using auto-scaling
               then you probably want to set it to true unless you're manually
               managing the capacity provider strategies for each service.

- `ingress_cidrs` (List of string or [IngressCidrModel](#IngressCidrModel)) - List of CIDRs which will be allowed to communicate with
                       the container instances. This must include at least the
                       load-balancer subnets which will be associated with
                       services on this cluster.

- `node_security_groups` (List of string) - List of security group IDs which will be assigned to all container instances.

- `scaling_groups` (List of [ScalingGroupModel](#ScalingGroupModel)) - One or more `scaling_group` objects defining the EC2
                       Auto-Scaling Group(s) which will provide container
                       instances for the cluster.

- `subnet_ids` (List of string) - IDs of the subnets where container instances will be
                       created. These should be "private" subnets behind a NAT.

- `tags` (Dict[string:string]) - Tags to apply to the cluster and ASG EC2 instances.



### ScalingGroupModel

- `allow_imds1` (boolean) - Allow IMDSv1 metadata service for backward-compatibility.

- `desired_size` (integer) - **required** - The desired number of container instances in this scaling group.
  - If `auto_scaling_enabled` is true, then ECS may modify the desired size of the scaling group to match demand.

- `extra_node_user_data` (string) - String to be appended to the user data of the scaling
                       group's nodes. This can be used to install additional
                       packages, modify the hosts file, etc.
  - **Default:** ``
  - **Warning:** Changing this value will trigger the replacement of all nodes in this group.

- `in_default_cps` (boolean) - When true, this scaling group will participate in the
                       default capacity provider strategy for the cluster. This
                       option has no effect if `auto_scaling_enabled` is false.
  - **Default:** `True`
  - [Changing instance types with auto-scaling enabled](EcsCluster_NodeTypeChangeWithAutoScaling.md)

- `key_name` (string) - **required** - The name of the SSH key to assign when creating container instances.

- `max_instance_lifetime_days` (integer) - The maximum amount of time, in seconds, that an instance
          can be in service. The default is null. If specified, the value must
          be greater than 1. This value will *only* apply to this autoscaling
          group.

- `max_size` (integer) - **required** - The maximum number of container instances allowed in this scaling group.

- `name` (string) - **required** - The name to assign the scaling group.

- `node_type` (string) - **required** - The EC2 instance type of the container instances in this scaling group.

- `tags` (Dict[string:string]) - Tags to apply to this ASG's EC2 instances.

- `weight` (integer) - Sets the weight of the scaling group within the default
                       capacity provider strategy. This option has no effect if
                       `auto_scaling_enabled` is false.
  - **Default:** `1`
  - **See also:** [AWS::ECS::Service CapacityProviderStrategyItem](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-ecs-service-capacityproviderstrategyitem.html#cfn-ecs-service-capacityproviderstrategyitem-weight)



### IngressCidrModel

- `cidr` (string) - **required** - CIDR to allow

- `description` (string) - Description of CIDR to note on the SG rule

