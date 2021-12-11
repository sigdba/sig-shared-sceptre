## Parameters

- `ClusterArn` (String) - **required**
- `DesiredCount` (Number)
  - **Default:** `1`
- `ListenerArn` (String) - **required**
- `MaximumPercent` (Number)
  - **Default:** `200`
- `MinimumHealthyPercent` (Number)
  - **Default:** `100`
- `VpcId` (String) - **required**


## sceptre_user_data

- `containers` (List of [ContainerModel](#ContainerModel)) - **required**
- `efs_volumes` (List of [EfsVolumeModel](#EfsVolumeModel))
- `placement_strategies` (List of [PlacementStrategyModel](#PlacementStrategyModel))
  - **Default:** `[{'field': 'memory', 'type': 'binpack'}]`
- `schedule` (List of [ScheduleModel](#ScheduleModel))


### ContainerModel

- `image` (string)
- `image_build` ([ImageBuildModel](#ImageBuildModel))
- `container_port` (integer)
- `port_mappings` (List of [PortMappingModel](#PortMappingModel))
- `container_memory_reservation` (integer)
- `env_vars` (Dict[string:string])
- `health_check` ([HealthCheckModel](#HealthCheckModel))
- `links` (List of string)
- `mount_points` (List of [MountPointModel](#MountPointModel))
- `rules` (List of [RuleModel](#RuleModel))
- `secrets` (Dict[string:string])
- `target_group_arn` (string)
- `container_memory` (integer)
  - **Default:** `512`
- `name` (string)
  - **Default:** `main`
- `protocol` (string)
  - **Default:** `HTTP`
- `target_group` ([TargetGroupModel](#TargetGroupModel))
  - **Default:** `{'attributes': {}}`


#### ImageBuildModel

- `codebuild_project_name` (string) - **required**
- `ecr_repo_name` (string) - **required**
- `env_vars` (List of [EnvironmentVariableModel](#EnvironmentVariableModel))


##### EnvironmentVariableModel

- `name` (string) - **required**
- `value` (string) - **required**
- `type` (string)
  - **Default:** `PLAINTEXT`


#### PortMappingModel

- `container_port` (integer) - **required**


#### HealthCheckModel

- `path` (string)
- `healthy_threshold_count` (integer)
- `interval_seconds` (integer)
  - **Default:** `60`
- `timeout_seconds` (integer)
  - **Default:** `30`
- `unhealthy_threshold_count` (integer)
  - **Default:** `5`
- `http_code` (string)
  - **Default:** `200-399`


#### MountPointModel

- `container_path` (string) - **required**
- `source_volume` (string) - **required**
- `read_only` (boolean)
  - **Default:** `False`


#### RuleModel

- `path` (string) - **required**
- `host` (string)
- `priority` (integer)


#### TargetGroupModel

- `attributes` (Dict[string:string])


### EfsVolumeModel

- `name` (string) - **required**
- `fs_id` (string) - **required**
- `root_directory` (string)


### PlacementStrategyModel

- `field` (string) - **required**
- `type` (string) - **required**


### ScheduleModel

- `cron` (string) - **required**
- `desired_count` (integer) - **required**
- `description` (string)
  - **Default:** `ECS service scheduling rule`
