#!/usr/bin/env python3


from typing import List, Optional, Dict
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

    # TODO: Validate iops


class SecurityGroupAllowModel(BaseModel):
    cidr: str
    description: str
    protocol = "tcp"
    from_port: Optional[int]
    to_port: Optional[int]

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


class UserDataModel(BaseModel):
    instance_name: str
    ami: AmiModel
    erpRole: str
    backups_enabled = True
    private_ip_address: Optional[str]
    allow_api_termination = False
    ebs_volumes: List[EbsVolumeModel] = []
    security_group = SecurityGroupModel()
    security_group_ids: List[str] = []
    instance_extra_props = {}
    instance_tags: Dict[str, str] = {}

    # TODO: Add check for duplicate drive letters
    # TODO: Add EFS mounts (needed here for SG updates?)
    # TODO: Add backups
