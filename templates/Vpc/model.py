from typing import List, Optional

from pydantic import BaseModel, validator

#
# IMPORTANT: The following classes are DATA CLASSES using pydantic.
#            DO NOT add behavior to them beyond input validation. Use functions
#            instead.
#


class SubnetModel(BaseModel):
    name: str
    kind: str
    availability_zone: str
    cidr: str
    map_public_ip_on_launch = False
    nat_eip_allocation_id: Optional[str]

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
    vpc_cidr: str
    vpc_name: Optional[str]
    vpc_extra_opts: dict = {}
    subnets: List[SubnetModel] = []
    customer_gateway: Optional[CustomerGatewayModel]
