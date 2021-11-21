import hashlib
import os.path

from troposphere import Ref, Sub, GetAtt, Tags
from troposphere.iam import Role, Policy
from troposphere.ec2 import SecurityGroup, Instance, Volume, MountPoint

from model import *
from util import *


def instance_sg(user_data):
    name = f"{user_data.instance_name}-sg"
    return add_resource(
        SecurityGroup(
            "InstanceSg",
            GroupName=name,
            VpcId=Ref("VpcId"),
            GroupDescription=f"Primary security group for {user_data.instance_name}",
            SecurityGroupEgress=user_data.security_group.egress,
            SecurityGroupIngress=user_data.security_group.ingress,
            Tags=Tags(Name=name),
        )
    )


def ebs_volume(inst_name, vol):
    opts = {}

    if vol.iops:
        opts["Iops"] = vol.iops
    if vol.throughput_mbs:
        opts["Throughput"] = vol.throughput_mbs

    return add_resource(
        Volume(
            f"EbsVolumeLETTER{vol.device_letter}",
            AvailabilityZone=Ref("AvailabilityZone"),
            Size=vol.size_gb,
            VolumeType=vol.vol_type,
            Tags=[
                {"Key": "Name", "Value": f"{inst_name}: {vol.mount_point}"},
                {"Key": "erp:mount_point", "Value": vol.mount_point},
                *[{"Key": k, "Value": v} for k, v in vol.tags.items()],
            ],
            **opts,
        )
    )


def ebs_volumes(user_data):
    return [ebs_volume(user_data.instance_name, v) for v in user_data.ebs_volumes]


def instance(user_data):
    opts = {}

    if user_data.private_ip_address:
        opts["PrivateIpAddress"] = user_data.private_ip_address
    if user_data.ami.user_data:
        opts["UserData"] = user_data.ami.user_data

    return add_resource(
        Instance(
            "Instance",
            DisableApiTermination=not user_data.allow_api_termination,
            ImageId=user_data.ami.ami_id,
            InstanceType=Ref("InstanceType"),
            KeyName=Ref("KeyPairName"),
            SecurityGroupIds=[
                GetAtt(instance_sg(user_data), "GroupId"),
                *user_data.security_group_ids,
            ],
            SubnetId=Ref("SubnetId"),
            Tags=Tags(Name=user_data.instance_name, **user_data.instance_tags),
            Volumes=[
                MountPoint(
                    Device=f"/dev/xvd{v.device_letter}",
                    VolumeId=Ref(ebs_volume(user_data.instance_name, v)),
                )
                for v in user_data.ebs_volumes
            ],
            **opts,
            **user_data.instance_extra_props,
        )
    )


def sceptre_handler(sceptre_user_data):
    add_param("VpcId", Type="AWS::EC2::VPC::Id")
    add_param("SubnetId", Type="AWS::EC2::Subnet::Id")
    add_param("AvailabilityZone", Type="AWS::EC2::AvailabilityZone::Name")
    add_param("InstanceType", Type="String")
    add_param("KeyPairName", Type="AWS::EC2::KeyPair::KeyName")

    user_data = UserDataModel(**sceptre_user_data)

    instance(user_data)

    return TEMPLATE.to_json()
