from troposphere import Ref, Sub, Join, Tags
from troposphere.efs import FileSystem, MountTarget, BackupPolicy
from troposphere.ec2 import SecurityGroup, SecurityGroupRule

from model import UserDataModel
from util import (
    add_resource,
    add_param,
    add_output,
    opts_from,
    opts_with,
    clean_title,
    TEMPLATE,
)

EFS_PORT = 2049


def r_filesystem(user_data, name):
    return add_resource(
        FileSystem(
            "FileSystem",
            BackupPolicy=BackupPolicy(
                Status="ENABLED" if user_data.auto_backups_enabled else "DISABLED"
            ),
            FileSystemTags=Tags(Name=name, **user_data.filesystem_tags),
            **user_data.filesystem_extra_opts,
        )
    )


def allow_ingress(allow):
    return SecurityGroupRule(
        FromPort=EFS_PORT,
        ToPort=EFS_PORT,
        IpProtocol="tcp",
        **opts_from(
            allow,
            Description="description",
            CidrIp="cidr",
            SourceSecurityGroupId="sg_id",
        ),
    )


def r_source_security_group(fs_name):
    sg_name = Sub("${AWS::StackName}-SourceSG")
    return add_resource(
        SecurityGroup(
            "SourceSecurityGroup",
            GroupDescription=Join(
                "", ["Members of this group can access EFS: ", fs_name]
            ),
            GroupName=sg_name,
            Tags=Tags(Name=sg_name),
            VpcId=Ref("VpcId"),
        )
    )


def r_target_security_group(fs_name, user_data):
    sg_name = Sub("${AWS::StackName}-TargetSG")
    return add_resource(
        SecurityGroup(
            "TargetSecurityGroup",
            GroupDescription=Join("", ["Security group assigned to EFS: ", fs_name]),
            GroupName=sg_name,
            SecurityGroupEgress=[
                SecurityGroupRule(
                    CidrIp="0.0.0.0/0",
                    Description="Allow all outbound traffic from EFS",
                    FromPort=0,
                    ToPort=65535,
                    IpProtocol="-1",
                )
            ],
            SecurityGroupIngress=[
                SecurityGroupRule(
                    FromPort=EFS_PORT,
                    ToPort=EFS_PORT,
                    IpProtocol="tcp",
                    SourceSecurityGroupId=Ref("SourceSecurityGroup"),
                ),
                *[allow_ingress(a) for a in user_data.allow],
            ],
            Tags=Tags(Name=sg_name),
            VpcId=Ref("VpcId"),
        )
    )


def r_mount_target(filesystem, mt_model):
    return add_resource(
        MountTarget(
            clean_title(f"MountTargetIN{mt_model.subnet_id}"),
            FileSystemId=Ref(filesystem),
            SecurityGroups=[Ref("TargetSecurityGroup")],
            SubnetId=mt_model.subnet_id,
            **opts_with(IpAddress=mt_model.ip_address),
        )
    )


def sceptre_handler(sceptre_user_data):
    add_param(
        "VpcId",
        Type="AWS::EC2::VPC::Id",
        Description="ID of the VPC in which to create resources.",
    )

    if sceptre_user_data is None:
        # We're generating documetation. Return the template with just parameters.
        return TEMPLATE

    user_data = UserDataModel(**sceptre_user_data)

    name = (
        user_data.filesystem_name
        if user_data.filesystem_name
        else Ref("AWS::StackName")
    )

    fs = r_filesystem(user_data, name)
    add_output("FileSystemId", Ref(fs))

    add_output(
        "SourceSecurityGroup",
        Ref(r_source_security_group(name)),
        Description="Assign clients to this SG to access the volume",
    )
    r_target_security_group(name, user_data)

    for t in user_data.mount_targets:
        r_mount_target(fs, t)

    return TEMPLATE.to_json()
