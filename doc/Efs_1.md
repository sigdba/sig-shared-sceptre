## Parameters

- `VpcId` (AWS::EC2::VPC::Id) - **required**



## sceptre_user_data

- `filesystem_name` (string)

- `auto_backups_enabled` (boolean) - **required**

- `allow` (List of [AllowModel](#AllowModel))

- `mount_targets` (List of [MountTargetModel](#MountTargetModel))

- `filesystem_tags` (Dict)

- `filesystem_extra_opts` (Dict)



### AllowModel

- `cidr` (string)

- `sg_id` (string)

- `description` (string)



### MountTargetModel

- `subnet_id` (string) - **required**

- `ip_address` (string)

