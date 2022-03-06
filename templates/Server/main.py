import hashlib
import os.path

from functools import partial

from troposphere import Ref, Sub, GetAtt, Tags, FindInMap, ImportValue
from troposphere.cloudformation import AWSCustomObject
from troposphere.iam import Role, Policy, InstanceProfile
from troposphere.ec2 import (
    SecurityGroup,
    Instance,
    Volume,
    MountPoint,
    EIP,
    EIPAssociation,
)
from troposphere.route53 import RecordSet, RecordSetType
from troposphere.backup import (
    BackupPlan,
    BackupPlanResourceType,
    BackupRuleResourceType,
    BackupSelection,
    BackupSelectionResourceType,
    BackupVault,
    LifecycleResourceType,
)

from model import *
from util import *
from root_vol import root_vol_props


def ingress_for_allow(allow):
    base_opts = {
        "Description": allow.description,
        "FromPort": allow.from_port,
        "ToPort": allow.to_port,
        "IpProtocol": "-1" if allow.protocol == "any" else allow.protocol,
    }

    def gen():
        for cidr in allow.cidr:
            yield {
                **base_opts,
                "CidrIp": cidr,
            }
        if allow.sg_id:
            yield {
                **base_opts,
                "SourceSecurityGroupId": allow.sg_id,
                **opts_with(SourceSecurityGroupOwnerId=allow.sg_owner),
            }

    return list(gen())


def instance_sg(user_data):
    name = f"{user_data.instance_name}-sg"
    return add_resource(
        SecurityGroup(
            "InstanceSg",
            GroupName=name,
            VpcId=Ref("VpcId"),
            GroupDescription=f"Primary security group for {user_data.instance_name}",
            SecurityGroupEgress=user_data.security_group.egress,
            SecurityGroupIngress=[
                i for a in user_data.security_group.allow for i in ingress_for_allow(a)
            ],
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
    return [(v, ebs_volume(user_data.instance_name, v)) for v in user_data.ebs_volumes]


def r_instance_role(ip_model):
    policies = []
    if ip_model.policy_document:
        policies.append(ip_model.policy_document)
    if len(ip_model.allow) > 0:
        policies.append(
            Policy(
                PolicyName="inline_allow",
                PolicyDocument={
                    "Version": "2012-10-17",
                    "Statement": [allow_statement(a) for a in ip_model.allow],
                },
            )
        )
    return add_resource(
        Role(
            "InstanceRole",
            Description=Sub("Instance profile role for ${AWS::StackName}"),
            ManagedPolicyArns=ip_model.managed_policy_arns,
            Policies=policies,
            AssumeRolePolicyDocument={
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"Service": "ec2.amazonaws.com"},
                        "Action": "sts:AssumeRole",
                    }
                ],
            },
            Tags=Tags(**ip_model.role_tags),
            **opts_with(Path=ip_model.role_path),
            **ip_model.role_extra_opts,
        )
    )


def r_instance_profile(ip_model):
    return add_resource(
        InstanceProfile(
            "InstanceProfile",
            Roles=[Ref(r_instance_role(ip_model))],
            **opts_with(Path=ip_model.profile_path),
        )
    )


def ami_id(ami_model):
    if ami_model.ami_id:
        return ami_model.ami_id

    add_mapping(
        "AmiMap", {region: {"Ami": ami} for region, ami in ami_model.ami_map.items()}
    )
    return FindInMap("AmiMap", Ref("AWS::Region"), "Ami")


def instance(user_data, ebs_mods_vols):
    return add_resource(
        Instance(
            "Instance",
            DisableApiTermination=not user_data.allow_api_termination,
            ImageId=ami_id(user_data.ami),
            InstanceType=Ref("InstanceType"),
            KeyName=Ref("KeyPairName"),
            SecurityGroupIds=[
                GetAtt(instance_sg(user_data), "GroupId"),
                *user_data.security_group_ids,
            ],
            SubnetId=Ref("SubnetId"),
            Tags=Tags(
                Name=user_data.instance_name,
                **{**user_data.ami.instance_tags, **user_data.instance_tags},
            ),
            Volumes=[
                MountPoint(
                    Device=f"/dev/xvd{m.device_letter}",
                    VolumeId=Ref(v),
                )
                for m, v in ebs_mods_vols
            ],
            **opts_with(
                PrivateIpAddress=user_data.private_ip_address,
                UserData=user_data.ami.user_data_b64,
                IamInstanceProfile=(user_data.instance_profile, r_instance_profile),
            ),
            **troposphere_opts(Instance, **user_data.instance_extra_props),
        )
    )


def backup_plan_rule(vault_name, rule):
    lifecycle_opts = {}
    if rule.cold_storage_after_days:
        lifecycle_opts["MoveToColdStorageAfterDays"] = rule.cold_storage_after_days

    return BackupRuleResourceType(
        RuleName=rule.name,
        ScheduleExpression=rule.schedule,
        TargetBackupVault=vault_name,
        Lifecycle=LifecycleResourceType(
            DeleteAfterDays=rule.retain_days, **lifecycle_opts
        ),
        **rule.rule_extra_props,
    )


def backup_vault(vault):
    vault_name = vault.name if vault.name else Ref("AWS::StackName")

    opts = {}
    if vault.encryption_key_arn:
        opts["EncryptionKeyArn"] = vault.encryption_key_arn

    return add_resource(
        BackupVault(
            "BackupVault",
            BackupVaultName=vault_name,
            BackupVaultTags=vault.tags,
            **opts,
            **vault.vault_extra_props,
        )
    )


def backup_plan(backups):
    plan_name = backups.plan_name if backups.plan_name else Ref("AWS::StackName")

    if backups.vault:
        if backups.vault.create:
            vault_name = Ref(backup_vault(backups.vault))
        else:
            vault_name = backups.vault.name
    else:
        vault_name = "Default"

    return add_resource(
        BackupPlan(
            "BackupPlan",
            BackupPlan=BackupPlanResourceType(
                AdvancedBackupSettings=backups.advanced_backup_settings,
                BackupPlanName=plan_name,
                BackupPlanRule=[backup_plan_rule(vault_name, r) for r in backups.rules],
            ),
            BackupPlanTags=backups.plan_tags,
        )
    )


def backup_role():
    return add_resource(
        Role(
            "BackupRole",
            AssumeRolePolicyDocument={
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"Service": ["backup.amazonaws.com"]},
                        "Action": ["sts:AssumeRole"],
                    }
                ],
            },
            ManagedPolicyArns=[
                "arn:aws:iam::aws:policy/service-role/AWSBackupServiceRolePolicyForBackup"
            ],
        )
    )


def backup_selection(backups, plan, ebs_mods_vols):
    return add_resource(
        BackupSelection(
            "BackupSelection",
            BackupPlanId=Ref(plan),
            BackupSelection=BackupSelectionResourceType(
                SelectionName=Ref("AWS::StackName"),
                IamRoleArn=GetAtt(backup_role(), "Arn"),
                Resources=[
                    Sub(
                        "arn:${AWS::Partition}:ec2:${AWS::Region}:${AWS::AccountId}:instance/${Instance}"
                    ),
                    *[
                        Sub(
                            "arn:${AWS::Partition}:ec2:${AWS::Region}:${AWS::AccountId}:volume/${%s}"
                            % v.title
                        )
                        for _, v in ebs_mods_vols
                    ],
                ],
            ),
        )
    )


def allow_statement(allow):
    return {
        "Effect": "Allow",
        "Action": allow.action,
        "Resource": allow.resource,
        **opts_with(Condition=allow.condition),
    }


class NsUpdate(AWSCustomObject):
    resource_type = "Custom::NsUpdate"
    props = {
        "ServiceToken": (str, True),
    }


def ns_entry_nsupdate(nsu_model, record_type, name, value):
    lambda_arn = (
        nsu_model.lambda_arn
        if nsu_model.lambda_arn is not None
        else ImportValue(nsu_model.lambda_arn_export_name)
    )

    name = f"{name}.{nsu_model.domain}"
    parts = name.split(".", nsu_model.zone_splits_at)
    zone = parts[-1]
    record = ".".join(parts[:-1])

    args = {
        nsu_model.lambda_record_type_key: record_type,
        nsu_model.lambda_record_key: record,
        nsu_model.lambda_zone_key: zone,
        nsu_model.lambda_value_key: value,
        **nsu_model.lambda_props,
    }

    return add_resource(
        NsUpdate(
            clean_title("NsUpdateFor{}".format(name)),
            validation=False,
            ServiceToken=lambda_arn,
            **args,
        )
    )


def ns_entry_route53(r53_model, record_type, name, value):
    if r53_model.hosted_zone_id:
        opts = {"HostedZoneId": r53_model.hosted_zone_id}
    else:
        opts = {"HostedZoneName": r53_model.domain}
    return add_resource(
        RecordSetType(
            clean_title("RecordSetFor{}".format(name)),
            Name=f"{name}.{r53_model.domain}",
            Type=record_type,
            TTL="300",
            ResourceRecords=[value],
            **opts,
        )
    )


def ns_entry_fn(user_data):
    r53 = user_data.route53
    if r53:
        return partial(ns_entry_route53, r53)

    nsupdate_model = user_data.ns_update
    if nsupdate_model is not None:
        return partial(ns_entry_nsupdate, nsupdate_model)

    # If no DNS configuration was provided, return a no-op function
    return lambda t, n, v: None


def attach_eip(user_data, inst):
    if not user_data.allocate_eip:
        return
    eip = add_resource(
        EIP(
            "Eip",
            Domain="vpc",
            InstanceId=Ref(inst),
            Tags=Tags(Name=Ref("AWS::StackName")),
        )
    )


def sceptre_handler(sceptre_user_data):
    add_param("VpcId", Type="AWS::EC2::VPC::Id")
    add_param("SubnetId", Type="AWS::EC2::Subnet::Id")
    add_param("AvailabilityZone", Type="AWS::EC2::AvailabilityZone::Name")
    add_param("InstanceType", Type="String")
    add_param(
        "KeyPairName",
        Type="AWS::EC2::KeyPair::KeyName",
        Description="SSH keypair used to access the server",
    )

    if sceptre_user_data is None:
        # We're generating documetation. Return the template with just parameters.
        return TEMPLATE

    user_data = UserDataModel(**sceptre_user_data)

    ebs_models_and_volumes = ebs_volumes(user_data)
    ec2_inst = instance(user_data, ebs_models_and_volumes)
    root_vol_props(ec2_inst, user_data)

    if user_data.backups_enabled:
        plan = backup_plan(user_data.backups)
        backup_selection(user_data.backups, plan, ebs_models_and_volumes)

    ns_entry_fn(user_data)("A", user_data.instance_name, GetAtt(ec2_inst, "PrivateIp"))
    attach_eip(user_data, ec2_inst)

    add_export("InstanceId", Sub("${AWS::StackName}-InstanceId"), Ref(ec2_inst))
    add_export("InstanceSg", Sub("${AWS::StackName}-InstanceSg"), Ref("InstanceSg"))

    return TEMPLATE.to_json()
