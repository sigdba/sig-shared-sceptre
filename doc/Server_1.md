## Parameters

- `AvailabilityZone` (AWS::EC2::AvailabilityZone::Name) - **required**
- `InstanceType` (String) - **required**
- `KeyPairName` (AWS::EC2::KeyPair::KeyName) - **required** - SSH keypair used to access the server
- `SubnetId` (AWS::EC2::Subnet::Id) - **required**
- `VpcId` (AWS::EC2::VPC::Id) - **required**


## sceptre_user_data

- `instance_name` (string) - **required**
- `ami` ([AmiModel](#AmiModel)) - **required**
- `backups_enabled` (boolean) - **required**
- `private_ip_address` (string) - Provide a fixed private IP address for the instance. If unspecified the instance will receive a random address within its subnet.
  - **See Also:** (AWS::EC2::Instance - PrivateIpAddress)[https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-ec2-instance.html#cfn-ec2-instance-privateipaddress]
- `ebs_volumes` (List of [EbsVolumeModel](#EbsVolumeModel)) - Additional EBS volumes to attach to the instance.
- `security_group_ids` (List of string)
- `instance_tags` (Dict[string:string])
- `instance_profile` ([ProfileModel](#ProfileModel))
- `backups` ([BackupsModel](#BackupsModel)) - Additional backup configuration
  - **Default:** If `backups_enabled` is `True` and `backups` is unspecified, then a simple daily backup plan will be created with 30-day retention.
- `allow_api_termination` (boolean)
  - **Default:** `False`
- `security_group` ([SecurityGroupModel](#SecurityGroupModel))
  - **Default:** `{'egress': [{'CidrIp': '0.0.0.0/0', 'Description': 'Allow all outbound', 'FromPort': '-1', 'ToPort': '-1', 'IpProtocol': '-1'}], 'allow': []}`
- `instance_extra_props` (Dict)


### AmiModel

- `ami_id` (string) - **required**
- `user_data_b64` (string)
- `commands` (List of string)


### EbsVolumeModel

- `size_gb` (integer) - **required**
- `mount_point` (string) - **required**
- `device_letter` (string) - **required**
- `tags` (Dict[string:string])
- `iops` (integer)
- `throughput_mbs` (integer)
- `extra_props` (List of Dict)
- `vol_type` (string)
  - **Default:** `gp3`


### ProfileModel

- `profile_path` (string)
- `role_path` (string)
- `allow` (List of [IamAllowModel](#IamAllowModel))
- `managed_policy_arns` (List of string)
- `policy_document` (Dict)
- `role_tags` (Dict)
- `role_extra_opts` (Dict)


#### IamAllowModel

- `action` (string or List of string) - **required**
- `resource` (string or List of string) - **required**
- `condition` (Dict)


### BackupsModel

- `vault` ([BackupVaultModel](#BackupVaultModel))
- `plan_name` (string)
- `plan_tags` (Dict[string:string])
- `rules` (List of [BackupRuleModel](#BackupRuleModel))
  - **Default:** `[{'name': 'Daily', 'retain_days': 30, 'cold_storage_after_days': None, 'schedule': 'cron(0 0 * * ? *)', 'rule_extra_props': {}}]`
- `advanced_backup_settings` (List)


#### BackupVaultModel

- `name` (string)
- `tags` (Dict[string:string])
- `encryption_key_arn` (string)
- `create` (boolean)
  - **Default:** `False`
- `vault_extra_props` (Dict)


#### BackupRuleModel

- `name` (string) - **required**
- `retain_days` (integer) - **required**
- `cold_storage_after_days` (integer)
- `schedule` (string) - **required**
- `rule_extra_props` (Dict)


### SecurityGroupModel

- `egress` (List of Dict[string:string])
  - **Default:** `[{'CidrIp': '0.0.0.0/0', 'Description': 'Allow all outbound', 'FromPort': '-1', 'ToPort': '-1', 'IpProtocol': '-1'}]`
- `allow` (List of [SecurityGroupAllowModel](#SecurityGroupAllowModel))


#### SecurityGroupAllowModel

- `cidr` (string) - **required**
- `description` (string) - **required**
- `from_port` (integer) - **required**
- `to_port` (integer) - **required**
- `protocol` (string)
  - **Default:** `tcp`
