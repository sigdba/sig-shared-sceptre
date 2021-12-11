## Parameters

- `VpcId` (String) - **required**


## sceptre_user_data

- `listeners` (List of [ListenerModel](#ListenerModel)) - **required**
- `subnet_ids` (List of string) - **required**
- `domain` (string)
- `internet_facing` (boolean) - **required**
- `access_logs` ([AccessLogsModel](#AccessLogsModel))
- `allow_cidrs` (List of string)
- `attributes` (Dict[string:string])
- `elb_security_groups` (List of string)
- `elb_tags` (Dict[string:string])
- `hosted_zone_id` (string)
- `ns_update` ([NsUpdateModel](#NsUpdateModel))
- `name` (string)
  - **Default:** `${AWS::StackName}`
- `certificate_validation_method` (string)
  - **Default:** `DNS`


### ListenerModel

- `hostnames` (List of [HostnameModel](#HostnameModel))
- `protocol` (string) - **required**
- `port` (integer) - **required**
- `https_redirect_to` (integer)
- `rules` (List of [RuleModel](#RuleModel))
- `default_action` ([ActionModel](#ActionModel))
  - **Default:** `{'fixed_response': None, 'health_check': None, 'redirect': None, 'target_group_attributes': {'stickiness.enabled': 'true', 'stickiness.type': 'lb_cookie'}, 'targets': [], 'target_port': 8080, 'target_protocol': 'HTTP'}`


#### HostnameModel

- `hostname` (string) - **required**
- `certificate_arn` (string)


#### RuleModel

- `fixed_response` ([FixedResponseModel](#FixedResponseModel))
- `health_check` ([HealthCheckModel](#HealthCheckModel))
- `redirect` ([RedirectModel](#RedirectModel))
- `target_group_attributes` (Dict[string:string])
- `targets` (List of [TargetModel](#TargetModel))
- `target_port` (integer)
  - **Default:** `8080`
- `target_protocol` (string)
  - **Default:** `HTTP`
- `input_values` (Dict)
- `paths` (List of string)
- `hosts` (List of string)
- `match_query_string` (List of [QueryStringMatchModel](#QueryStringMatchModel))
- `priority` (integer)


##### FixedResponseModel

- `message_body` (string)
- `content_type` (string)
  - **Default:** `text/plain`
- `status_code` (integer)
  - **Default:** `200`


##### HealthCheckModel

- `interval_seconds` (integer)
- `path` (string)
- `timeout_seconds` (integer)
- `protocol` (string)
- `healthy_threshold_count` (integer)
- `unhealth_threshold_count` (integer)


##### RedirectModel

- `host` (string)
- `path` (string)
- `port` (integer)
- `protocol` (string)
- `query` (string)
- `status_code` (integer)
  - **Default:** `302`


##### TargetModel

- `id` (string) - **required**
- `port` (integer)


##### QueryStringMatchModel

- `key` (string) - **required**
- `value` (string) - **required**


#### ActionModel

- `fixed_response` ([FixedResponseModel](#FixedResponseModel))
- `health_check` ([HealthCheckModel](#HealthCheckModel))
- `redirect` ([RedirectModel](#RedirectModel))
- `target_group_attributes` (Dict[string:string])
- `targets` (List of [TargetModel](#TargetModel))
- `target_port` (integer)
  - **Default:** `8080`
- `target_protocol` (string)
  - **Default:** `HTTP`


### AccessLogsModel

- `bucket` (string)
- `enabled` (boolean)
  - **Default:** `True`
- `retain_days` (integer)
  - **Default:** `90`
- `prefix_expr` (string)
  - **Default:** `${AWS::StackName}-access.`


### NsUpdateModel

- `lambda_arn` (string)
- `lambda_arn_export_name` (string)
- `lambda_props` (Dict[string:string])
- `lambda_record_key` (string) - **required**
- `lambda_zone_key` (string) - **required**
- `lambda_record_type_key` (string)
  - **Default:** `RecordType`
- `lambda_value_key` (string)
  - **Default:** `Value`
- `zone_splits_at` (integer)
  - **Default:** `1`
