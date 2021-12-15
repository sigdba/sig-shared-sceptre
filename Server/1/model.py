from base64 import b64encode
from typing import List, Optional, Dict, Union
from pydantic import BaseModel, ValidationError, validator, root_validator, Field
from util import debug

#
# IMPORTANT: The following classes are DATA CLASSES using pydantic.
#            DO NOT add behavior to them beyond input validation. Use functions
#            instead.
#


class EbsVolumeModel(BaseModel):
    size_gb: int
    vol_type = "gp3"
    mount_point: str
    device_letter: str
    tags: Dict[str, str] = {}
    iops: Optional[int]
    throughput_mbs: Optional[int]
    extra_props: List[dict] = []


class SecurityGroupAllowModel(BaseModel):
    cidr: str
    description: str
    protocol = "tcp"
    from_port: int
    to_port: int

    def parse_port(port):
        if isinstance(port, int):
            return (port, port)
        p = port.strip()
        if p == "any":
            return (-1, -1)
        elif p.isnumeric():
            return (int(p), int(p))
        elif "-" in p:
            l = [s.strip() for s in p.split("-")]
            if len(l) != 2 or not all(s.isnumeric() for s in l):
                raise ValueError(f"Invalid port specification: '{port}'")
            return (int(l[0]), int(l[1]))
        raise ValueError(f"Invalid port specification: '{port}'")

    @root_validator(pre=True)
    def handle_port(cls, values):
        if "from_port" in values and "to_port" in values:
            if "port" in values:
                raise ValueError("port cannot be specified with from_ and to_port")
        elif "from_port" in values or "to_port" in values:
            raise ValueError("from_port and to_port must be specified together")
        elif "port" in values:
            f, t = cls.parse_port(values["port"])
            values["from_port"] = f
            values["to_port"] = t
            del values["port"]
        else:
            raise ValueError("Either port or from_ and to_port must be specified")

        return values


class SecurityGroupModel(BaseModel):
    egress: List[Dict[str, str]] = [
        {
            "CidrIp": "0.0.0.0/0",
            "Description": "Allow all outbound",
            "FromPort": "-1",
            "ToPort": "-1",
            "IpProtocol": "-1",
        }
    ]
    allow: List[SecurityGroupAllowModel] = []


class AmiModel(BaseModel):
    ami_id: Optional[str]
    ami_map: Optional[Dict[str, str]]
    user_data_b64: Optional[str]
    commands: Optional[List[str]]
    instance_tags: Dict[str, str] = {}

    @root_validator
    def require_ami_or_map(cls, values):
        if values["ami_id"] is None and values["ami_map"] is None:
            raise ValueError("One of ami_id or ami_map is required")
        if values["ami_id"] and values["ami_map"]:
            raise ValueError("ami_id and ami_map are mutually exclusive")
        return values

    @root_validator
    def encode_user_data(cls, values):
        cs = "utf-8"
        if values.get("commands", None):
            if values.get("user_data_b64", None):
                raise ValueError(
                    "user_data_b64 and commands cannot be specified together"
                )
            values["user_data_b64"] = b64encode(
                "\n".join(["#!/bin/bash"] + values["commands"]).encode(cs)
            ).decode(cs)
        return values


class BackupVaultModel(BaseModel):
    create = False
    name: Optional[str]
    tags: Dict[str, str] = {}
    encryption_key_arn: Optional[str]
    vault_extra_props = {}

    @root_validator
    def require_name_when_not_creatingz(cls, values):
        if (not values["create"]) and (values["name"] is None):
            raise ValueError("name must be specified in vault object")
        return values


class BackupRuleModel(BaseModel):
    name: str
    retain_days: int
    cold_storage_after_days: Optional[int]
    schedule: str
    rule_extra_props = {}

    # TODO: Validate retain > cold_storage


class BackupsModel(BaseModel):
    vault: Optional[BackupVaultModel]
    plan_name: Optional[str]
    plan_tags: Dict[str, str] = {}
    rules: List[BackupRuleModel] = [
        BackupRuleModel(name="Daily", retain_days=30, schedule="cron(0 0 * * ? *)")
    ]
    advanced_backup_settings: list = []

    # TODO: Require at least one rule
    # TODO: Add "shortcut" rules
    # TODO: Disallow vault and vault_name
    # TODO: vault implies create_vault
    # TODO: create_vault=False excludes vault


class IamAllowModel(BaseModel):
    action: Union[str, List[str]]
    resource: Union[str, List[str]]
    condition: Optional[dict]


class ProfileModel(BaseModel):
    profile_path: Optional[str]
    role_path: Optional[str]
    allow: List[Union[IamAllowModel, List[IamAllowModel]]] = []
    managed_policy_arns: List[str] = []
    policy_document: Optional[dict]
    role_tags: dict = {}
    role_extra_opts: dict = {}

    @validator("allow")
    def flatten_allow_list(cls, v):
        def f(v):
            queue = v
            while len(queue) > 0:
                item = queue.pop(0)
                if type(item) is list:
                    queue.extend(item)
                else:
                    yield item

        return list(f(v))


class UserDataModel(BaseModel):
    instance_name: str
    ami: AmiModel
    backups_enabled: bool
    backups = Field(
        BackupsModel(),
        description="Additional backup configuration",
        default_description="If `backups_enabled` is `True` and `backups` is unspecified, then a simple daily backup plan will be created with 30-day retention.",
    )
    private_ip_address: Optional[str] = Field(
        description="Provide a fixed private IP address for the instance. If unspecified the instance will receive a random address within its subnet.",
        notes=[
            "**See Also:** (AWS::EC2::Instance - PrivateIpAddress)[https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-ec2-instance.html#cfn-ec2-instance-privateipaddress]"
        ],
    )
    allow_api_termination = False
    ebs_volumes: List[EbsVolumeModel] = Field(
        [], description="Additional EBS volumes to attach to the instance."
    )
    security_group = SecurityGroupModel()
    security_group_ids: List[str] = []
    instance_extra_props = {}
    instance_tags: Dict[str, str] = {}
    instance_profile: Optional[ProfileModel]

    @validator("ebs_volumes")
    def check_for_duplicate_drive_letters(cls, v):
        letters = [m.device_letter for m in v]
        if len(set(letters)) < len(letters):
            raise ValueError("Duplicate device_letters specified in ebs_volumes")
        return v

    # TODO: Add EFS mounts (needed here for SG updates?)
    # TODO: Add backups
    # TODO: Add instance profile and role
    # TODO: Route53 integration
