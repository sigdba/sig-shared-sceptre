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
  - **See Also:** [AWS::EC2::Instance - PrivateIpAddress](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-ec2-instance.html#cfn-ec2-instance-privateipaddress)

- `ebs_volumes` (List of [EbsVolumeModel](#EbsVolumeModel)) - Additional EBS volumes to attach to the instance.

- `root_volume_tags` (Dict[string:string])

- `root_volume_size` (integer)

- `security_group_ids` (List of string)

- `instance_tags` (Dict[string:string])

- `instance_profile` ([ProfileModel](#ProfileModel))

- `stack_outputs` (List of [OutputModel](#OutputModel)) - Arbitrary [CloudFormation Stack Outputs](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/outputs-section-structure.html)
                       with optional exports.

- `route53` ([Route53Model](#Route53Model))

- `ns_update` ([NsUpdateModel](#NsUpdateModel)) - Specifies how DNS entries should be updated when not using Route53.

- `backups` ([BackupsModel](#BackupsModel)) - Additional backup configuration
  - **Default:** If `backups_enabled` is `True` and `backups` is unspecified, then a simple daily backup plan will be created with 30-day retention.

- `allow_api_termination` (boolean)
  - **Default:** `False`

- `security_group` ([SecurityGroupModel](#SecurityGroupModel))
  - **Default:** `{'egress': [{'CidrIp': '0.0.0.0/0', 'Description': 'Allow all outbound', 'FromPort': '-1', 'ToPort': '-1', 'IpProtocol': '-1'}], 'allow': []}`

- `instance_extra_props` (Dict)

- `allocate_eip` (boolean)
  - **Default:** `False`



### SecurityGroupModel

- `egress` (List of Dict[string:string])
  - **Default:** `[{'CidrIp': '0.0.0.0/0', 'Description': 'Allow all outbound', 'FromPort': '-1', 'ToPort': '-1', 'IpProtocol': '-1'}]`

- `allow` (List of [SecurityGroupAllowModel](#SecurityGroupAllowModel) or List of [SecurityGroupAllowModel](#SecurityGroupAllowModel))



#### SecurityGroupAllowModel

- `cidr` (string or List of string) - The IPv4 address range(s), in CIDR format. May be specified as a single string or a list of strings.
  - You must specify one of `cidr` or `sg_id` but not both.

- `sg_id` (string) - The ID of a security group whose members are allowed.
  - You must specify one of `cidr` or `sg_id` but not both.

- `sg_owner` (string) - The AWS account ID that owns the security group specified in `sg_id`. This value is required if the SG is in another account.

- `description` (string) - **required**

- `from_port` (integer) - **required**

- `to_port` (integer) - **required**

- `protocol` (string)
  - **Default:** `tcp`



### BackupsModel

- `vault` ([BackupVaultModel](#BackupVaultModel))

- `plan_name` (string)

- `plan_tags` (Dict[string:string])

- `rules` (List of [BackupRuleModel](#BackupRuleModel))
  - **Default:** `[{'name': 'Daily', 'retain_days': 30, 'cold_storage_after_days': None, 'schedule': 'cron(0 0 * * ? *)', 'rule_extra_props': {}}]`

- `advanced_backup_settings` (List)



#### BackupRuleModel

- `name` (string) - **required**

- `retain_days` (integer) - **required**

- `cold_storage_after_days` (integer)

- `schedule` (string) - **required**

- `rule_extra_props` (Dict)



#### BackupVaultModel

- `name` (string)

- `tags` (Dict[string:string])

- `encryption_key_arn` (string)

- `create` (boolean)
  - **Default:** `False`

- `vault_extra_props` (Dict)



### NsUpdateModel

- `lambda_arn` (string) - ARN of the Lambda function which provides NS update functionality.
  - One of `lambda_arn` or `lambda_arn_export_name` must be specified.

- `lambda_arn_export_name` (string) - Export name for the ARN of the Lambda function which provides NS update functionality.
  - One of `lambda_arn` or `lambda_arn_export_name` must be specified.

- `lambda_props` (Dict[string:string])

- `lambda_record_key` (string) - **required**

- `lambda_zone_key` (string) - **required**

- `domain` (string) - **required** - Server's DNS entry will be `<instance_name>.<ns_update.domain>`

- `lambda_record_type_key` (string)
  - **Default:** `RecordType`

- `lambda_value_key` (string)
  - **Default:** `Value`

- `zone_splits_at` (integer)
  - **Default:** `1`



### Route53Model

- `hosted_zone_id` (string)

- `domain` (string) - **required**



### OutputModel

- `name` (string) - **required** - The Logical ID of the export. Must be unique within the stack's outputs.

- `value` (string) - **required** - The value of the property returned by the aws cloudformation describe-stacks
                       command. This string will be passed to
                       [Fn::Sub](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/intrinsic-function-reference-sub.html)

- `description` (string)
  - **Default:** `A description of the output value.`

- `export_name` (string) - The name of the resource output to be exported for a cross-stack reference.
                       This must be unique within the account's exports.



### ProfileModel

- `profile_path` (string)

- `role_path` (string)

- `allow` (List of [IamAllowModel](#IamAllowModel) or List of [IamAllowModel](#IamAllowModel))

- `managed_policy_arns` (List of string)

- `policy_document` (Dict)

- `role_tags` (Dict)

- `role_extra_opts` (Dict)



#### IamAllowModel

- `action` (string or List of string) - **required**

- `resource` (string or List of string) - **required**

- `condition` (Dict)



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



### AmiModel

- `ami_id` (string) - ID of the AMI the server will be created from.
  - You must specify either `ami_id` or `ami_map` but not both.
  - **Warning** - Changing this value after the instance is created will trigger its replacement.

- `ami_map` (Dict[string:string]) - A mapping of AWS regions to AMI-IDs
  - You must specify either `ami_id` or `ami_map` but not both.
  - **Warning:** Changing an AMI ID after instance creation will trigger replacement.

- `user_data_b64` (string) - The user data to make available to the instance, base64-encoded. This is
                       typically commands to run on first boot.
  - **Warning:** Changing this value after the instance is created may trigger a reboot.
  - If `commands` is specified, this value will be ignored.

- `commands` (List of string) - List of commands to encode as user data
  - **Warning:** Changing this value after the instance is created may trigger a reboot.

- `instance_tags` (Dict[string:string])

