from base64 import b64encode
from typing import List, Optional, Dict, Union
from pydantic import BaseModel, ValidationError, validator, root_validator
from util import debug

#
# IMPORTANT: The following classes are DATA CLASSES using pydantic.
#            DO NOT add behavior to them beyond input validation. Use functions
#            instead.
#


class ScalingGroupModel(BaseModel):
    name: str
    key_name: str
    node_type: str
    max_size: int
    desired_size: int
    in_default_cps = True
    weight = 1


class UserDataModel(BaseModel):
    node_security_groups: List[str] = []
    ingress_cidrs: List[str] = []
    auto_scaling_enabled = True
    container_insights_enabled = False
    force_default_cps = False
    scaling_groups = List[ScalingGroupModel]
