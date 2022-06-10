from base64 import b64encode
from typing import List, Optional, Dict, Union
from pydantic import ValidationError, validator, root_validator, Field
from util import debug, BaseModel

#
# IMPORTANT: The following classes are DATA CLASSES using pydantic.
#            DO NOT add behavior to them beyond input validation. Use functions
#            instead.
#


class ScalingGroupModel(BaseModel):
    name: str = Field(description="The name to assign the scaling group.")
    key_name: str = Field(
        description="The name of the SSH key to assign when creating container instances."
    )
    node_type: str = Field(
        description="The EC2 instance type of the container instances in this scaling group."
    )
    max_size: int = Field(
        description="The maximum number of container instances allowed in this scaling group."
    )
    desired_size: int = Field(
        description="The desired number of container instances in this scaling group.",
        notes=[
            "If `auto_scaling_enabled` is true, then ECS may modify the desired size of the scaling group to match demand."
        ],
    )
    in_default_cps = Field(
        True,
        description="""When true, this scaling group will participate in the
                       default capacity provider strategy for the cluster. This
                       option has no effect if `auto_scaling_enabled` is false.""",
        notes=[
            "[Changing instance types with auto-scaling enabled](EcsCluster_NodeTypeChangeWithAutoScaling.md)"
        ],
    )
    weight = Field(
        1,
        description="""Sets the weight of the scaling group within the default
                       capacity provider strategy. This option has no effect if
                       `auto_scaling_enabled` is false.""",
        notes=[
            "**See also:** [AWS::ECS::Service CapacityProviderStrategyItem](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-ecs-service-capacityproviderstrategyitem.html#cfn-ecs-service-capacityproviderstrategyitem-weight)"
        ],
    )
    tags: Dict[str, str] = Field(
        {}, description="Tags to apply to this ASG's EC2 instances."
    )


class UserDataModel(BaseModel):
    node_security_groups: List[str] = Field(
        [],
        description="List of security group IDs which will be assigned to all container instances.",
    )
    ingress_cidrs: List[str] = Field(
        [],
        description="""List of CIDRs which will be allowed to communicate with
                       the container instances. This must include at least the
                       load-balancer subnets which will be associated with
                       services on this cluster.""",
    )
    auto_scaling_enabled = Field(
        True,
        description="When true, auto-scaling features will be enabled on the cluster based on ECS capacity providers.",
        notes=[
            """**Warning:** Once a capacity provider has been assigned to an ECS
               service it can be changed but it cannot be removed. Therefore,
               once auto-scaling has been enabled on a cluster, it will be
               necessary to remove all services before auto-scaling can be
               disabled again."""
        ],
    )
    container_insights_enabled = Field(
        False,
        description="When true, Container Insights will be enabled.",
        notes=[
            """Container Insights can be surprisingly expensive. Be sure to
               review the [CloudWatch Pricing page](https://aws.amazon.com/cloudwatch/pricing/)
               and note the pricing example for Container Insights."""
        ],
    )
    force_default_cps = Field(
        False,
        description="""When true, changes to the `scaling_groups` will trigger
                       an update of all services on the cluster, forcing them to
                       use the new default capacity provider(s). This setting
                       has no effect if `auto_scaling_enabled == false`. """,
        notes=[
            """This setting defaults to false, but if you're using auto-scaling
               then you probably want to set it to true unless you're manually
               managing the capacity provider strategies for each service."""
        ],
    )
    subnet_ids: List[str] = Field(
        [],
        description="""IDs of the subnets where container instances will be
                       created. These should be "private" subnets behind a NAT.""",
    )
    scaling_groups: List[ScalingGroupModel] = Field(
        [],
        description="""One or more `scaling_group` objects defining the EC2
                       Auto-Scaling Group(s) which will provide container
                       instances for the cluster.""",
    )
    tags: Dict[str, str] = Field(
        {}, description="Tags to apply to the cluster and ASG EC2 instances."
    )
    cluster_tags: Dict[str, str] = Field(
        {}, description="Tags to apply to the cluster."
    )
    asg_tags: Dict[str, str] = Field(
        {}, description="Tags to apply to all ASG EC2 instances."
    )
