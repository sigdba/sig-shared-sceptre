#!/usr/bin/env python3


from typing import List, Optional, Dict, Union
from pydantic import BaseModel, ValidationError, validator, root_validator

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
    ami_id: str
    user_data: Optional[str]


class BackupVaultModel(BaseModel):
    name: Optional[str]
    tags: Dict[str, str] = {}
    encryption_key_arn: Optional[str]
    vault_extra_props = {}


class BackupRuleModel(BaseModel):
    name: str
    retain_days: int
    cold_storage_after_days: Optional[int]
    schedule: str
    rule_extra_props = {}

    # TODO: Validate retain > cold_storage


class BackupsModel(BaseModel):
    vault: Optional[BackupVaultModel]
    vault_name: Optional[str]
    plan_name: Optional[str]
    plan_tags: Dict[str, str] = {}
    rules: List[BackupRuleModel] = [
        BackupRuleModel(name="Daily", retain_days=30, schedule="cron(0 0 * * ? *)")
    ]
    advanced_backup_settings: list = []

    # TODO: Require at least one rule
    # TODO: Add "shortcut" rules


class UserDataModel(BaseModel):
    instance_name: str
    ami: AmiModel
    erpRole: str
    backups_enabled: bool
    backups = BackupsModel()
    private_ip_address: Optional[str]
    allow_api_termination = False
    ebs_volumes: List[EbsVolumeModel] = []
    security_group = SecurityGroupModel()
    security_group_ids: List[str] = []
    instance_extra_props = {}
    instance_tags: Dict[str, str] = {}

    @validator("ebs_volumes")
    def check_for_duplicate_drive_letters(cls, v):
        letters = [m.device_letter for m in v]
        if len(set(letters)) < len(letters):
            raise ValueError("Duplicate device_letters specified in ebs_volumes")
        return v

    # TODO: Add EFS mounts (needed here for SG updates?)
    # TODO: Add backups
    # TODO: Add instance profile and role
