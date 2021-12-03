#!/usr/bin/env python3


from typing import List, Optional, Dict, Union
from pydantic import BaseModel, ValidationError, validator, root_validator
from util import debug

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


class UserDataModel(BaseModel):
    vpc_cidr: str
    vpc_name: Optional[str]
    subnets: List[SubnetModel] = []
