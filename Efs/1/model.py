from typing import List, Optional, Dict, Union
from pydantic import BaseModel, ValidationError, validator, root_validator
from util import debug

#
# IMPORTANT: The following classes are DATA CLASSES using pydantic.
#            DO NOT add behavior to them beyond input validation. Use functions
#            instead.
#


class AllowModel(BaseModel):
    cidr: Optional[str]
    sg_id: Optional[str]
    description: Optional[str]

    # TODO: Require one of cidr/sg_id


class MountTargetModel(BaseModel):
    subnet_id: str
    ip_address: Optional[str]


class UserDataModel(BaseModel):
    filesystem_name: Optional[str]
    auto_backups_enabled: bool
    filesystem_tags = {}
    filesystem_extra_opts = {}
    allow: List[AllowModel] = []
    mount_targets: List[MountTargetModel] = []
