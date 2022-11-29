from typing import List, Optional

from pydantic import Field, root_validator

from util import BaseModel

#
# IMPORTANT: The following classes are DATA CLASSES using pydantic.
#            DO NOT add behavior to them beyond input validation. Use functions
#            instead.
#


class AllowModel(BaseModel):
    cidr: Optional[str] = Field(
        description="Traffic from this CIDR will be allowed.",
        notes=["You must specify one of `cidr` or `sg_id` but not both."],
    )
    sg_id: Optional[str] = Field(
        description="Members of this security group will be allowed.",
        notes=["You must specify one of `cidr` or `sg_id` but not both."],
    )
    description: Optional[str] = Field(description="Description of this rule.")

    # TODO: Require one of cidr/sg_id


class MountTargetModel(BaseModel):
    subnet_id: str = Field(
        description="ID of the subnet in which to create this mount target."
    )
    ip_address: Optional[str] = Field(
        description="IP address to use for this mount target."
    )


class UserDataModel(BaseModel):
    filesystem_name: Optional[str] = Field(
        description="Name of the EFS volume to create."
    )
    auto_backups_enabled: bool = Field(
        description="When `true`, EFS auto-backups will be enabled for this volume."
    )
    filesystem_tags = Field({}, description="Tags to apply to this volume.")
    filesystem_extra_opts = Field(
        {},
        description="Additional options to apply to the EFS FileSystem object.",
        notes=[
            "**See:** [AWS::EFS::FileSystem](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-efs-filesystem.html)"
        ],
    )
    allow: List[AllowModel] = Field([], description="Rules to allow inbound traffic.")
    mount_targets: List[MountTargetModel] = Field(
        [], description="Mount targets to create."
    )
    separate_security_groups = Field(
        True,
        description="""When `True` a separate 'source' SG will be created and
                       members of this SG will be granted access to the NFS
                       ports. When `False`, a single SG will be created and used
                       both to grant access and as the SG on the mount targets.""",
        notes=[
            "**Note:** To avoid potential security issues, `separate_security_groups` must be `True` if `allow` is not empty."
        ],
    )

    @root_validator
    def separate_sgs_empty_allow(cls, values):
        if not values.get("separate_security_groups") and len(values["allow"]) > 0:
            raise ValueError(
                "`allow` must be empty when `separate_security_groups` is False"
            )
        return values
