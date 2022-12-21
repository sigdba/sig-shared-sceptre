from typing import List, Optional

from pydantic import validator, Field

from util import BaseModel

#
# IMPORTANT: The following classes are DATA CLASSES using pydantic.
#            DO NOT add behavior to them beyond input validation. Use functions
#            instead.
#


class RouteModel(BaseModel):
    dest_cidr: str = Field(
        description="The IPv4 CIDR block used for the destination match."
    )
    transit_gateway_id: Optional[str] = Field(
        description="The ID of a transit gateway."
    )
    carrier_gateway_id: Optional[str] = Field(
        description="The ID of the carrier gateway."
    )
    eggress_only_internet_gateway_id: Optional[str] = Field(
        description="The ID of the egress-only internet gateway."
    )
    gateway_id: Optional[str] = Field(
        description="The ID of an internet gateway or virtual private gateway attached to your VPC."
    )
    instance_id: Optional[str] = Field(
        description="The ID of a NAT instance in your VPC."
    )
    local_gateway_id: Optional[str] = Field(description="The ID of the local gateway.")
    nat_gateway_id: Optional[str] = Field(description="The ID of a NAT gateway.")
    network_interface_id: Optional[str] = Field(
        description="The ID of the network interface."
    )
    vpc_endpoint_id: Optional[str] = Field(
        description="The ID of a VPC endpoint. Supported for Gateway Load Balancer endpoints only."
    )
    vpc_peering_connection_id: Optional[str] = Field(
        description="The ID of a VPC peering connection."
    )


class SubnetModel(BaseModel):
    name: str
    kind: str
    availability_zone: str
    cidr: str
    map_public_ip_on_launch = False
    nat_eip_allocation_id: Optional[str]
    routes: List[RouteModel] = []

    # TODO: Allow nat_eip_allocation_id only on public subnets
    # TODO: Allow only alphanumeric and dash in subnet name

    @validator("kind")
    def subnet_kind(cls, v):
        assert v in ["public", "private"]
        return v


class CustomerGatewayModel(BaseModel):
    customer_asn = 65000
    amazon_asn: Optional[int]
    ip_address: str
    vpn_type = "ipsec.1"
    static_routes_only: bool
    tunnel_inside_cidr: Optional[str]
    static_route_cidrs: List[str] = []


class UserDataModel(BaseModel):
    vpc_cidr: str = Field(description="CIDR for the VPC")
    vpc_name: Optional[str]
    vpc_extra_opts: dict = {}
    subnets: List[SubnetModel] = []
    customer_gateway: Optional[CustomerGatewayModel]
