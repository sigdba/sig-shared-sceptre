#!/usr/bin/env python3


from typing import List, Optional, Dict
from pydantic import BaseModel, ValidationError, validator

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
    ingress: List[Dict[str, str]] = []


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
    # TODO: Add EFS mount info? Or just let the user pass tags? Or maybe that belongs in Ansible?
