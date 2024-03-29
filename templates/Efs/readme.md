# Efs

Creates an EFS volume and associated resources.

## Parameters

- `VpcId` (AWS::EC2::VPC::Id) - **required** - ID of the VPC in which to create resources.



## sceptre_user_data

- `allow` (List of [AllowModel](#AllowModel)) - Rules to allow inbound traffic.

- `auto_backups_enabled` (boolean) - **required** - When `true`, EFS auto-backups will be enabled for this volume.

- `filesystem_extra_opts` (Dict) - Additional options to apply to the EFS FileSystem object.
  - **See:** [AWS::EFS::FileSystem](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-efs-filesystem.html)

- `filesystem_name` (string) - Name of the EFS volume to create.

- `filesystem_tags` (Dict) - Tags to apply to this volume.

- `mount_targets` (List of [MountTargetModel](#MountTargetModel)) - Mount targets to create.



### MountTargetModel

- `ip_address` (string) - IP address to use for this mount target.

- `subnet_id` (string) - **required** - ID of the subnet in which to create this mount target.



### AllowModel

- `cidr` (string) - Traffic from this CIDR will be allowed.
  - You must specify one of `cidr` or `sg_id` but not both.

- `description` (string) - Description of this rule.

- `sg_id` (string) - Members of this security group will be allowed.
  - You must specify one of `cidr` or `sg_id` but not both.

