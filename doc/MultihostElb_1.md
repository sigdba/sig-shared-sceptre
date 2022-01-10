## Parameters

- `VpcId` (String) - **required** - The ID of the VPC where the ECS cluster will be created.



## sceptre_user_data

- `listeners` (List of [ListenerModel](#ListenerModel)) - **required** - One listener object for each port the ELB should listen on.

- `subnet_ids` (List of string) - **required** - At least two subnet IDs within the VPC for the ELB to occupy.

- `domain` (string) - The domain to append to short hostnames used elsewhere in the template.
  - Any hostname specified in the configuration which does not contain a dot (.)
               will be treated as "short" and this value will be appended. If a
               short hostname is specified and `domain` has not been provided
               then an error will occur.

- `internet_facing` (boolean) - **required** - If `true` the ELB will be created accessible externally, otherwise it will be
                       created as an "internal" ELB.
  - **See Also:** [AWS::ElasticLoadBalancingV2::LoadBalancer](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-elasticloadbalancingv2-loadbalancer.html#cfn-elasticloadbalancingv2-loadbalancer-scheme)

- `access_logs` ([AccessLogsModel](#AccessLogsModel))

- `allow_cidrs` (List of string) - A list of CIDRs allowed to access the ELB.
  - **Default:** With `allow_cidrs` empty, if `elb_security_groups` has been provided, then no
                               security group will be created. Otherwise, a new
                               SG will be created allowing all traffic.

- `attributes` (Dict[string:string]) - ELB attributes
  - Settings in `access_logs` will modify related ELB attributes.
  - **See Also:** [AWS::ElasticLoadBalancingV2::LoadBalancer](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-elasticloadbalancingv2-loadbalancer.html#cfn-elasticloadbalancingv2-loadbalancer-scheme)

- `elb_security_groups` (List of string) - List if security group IDs to associate with the ELB.
  - If you specify this value and do not specify `allow_cidrs` then this stack will not create a security group.

- `elb_tags` (Dict[string:string]) - Tags to apply to the ELB object

- `hosted_zone_id` (string) - The Route53 hosted zone ID in which to create DNS entries for certificate
                       validation and for hostnames specified for
                       `listeners`.

- `ns_update` ([NsUpdateModel](#NsUpdateModel)) - Specifies how DNS entries should be updated when not using Route53.

- `name` (string)
  - **Default:** `${AWS::StackName}`

- `certificate_validation_method` (string) - The method by which AWS Certificate Manager (ACM) will validate generated certificates.
  - **Default:** `DNS`
  - **Allowed Values:** `DNS`, `EMAIL`
  - If you do not wish the stack to generate certificates, then you must provide
               `certificate_arn` values for each `hostname` entry specified
               under `listeners`.



### NsUpdateModel

- `lambda_arn` (string) - ARN of the Lambda function which provides NS update functionality.
  - One of `lambda_arn` or `lambda_arn_export_name` must be specified.

- `lambda_arn_export_name` (string) - Export name for the ARN of the Lambda function which provides NS update functionality.
  - One of `lambda_arn` or `lambda_arn_export_name` must be specified.

- `lambda_props` (Dict[string:string])

- `lambda_record_key` (string) - **required**

- `lambda_zone_key` (string) - **required**

- `lambda_record_type_key` (string)
  - **Default:** `RecordType`

- `lambda_value_key` (string)
  - **Default:** `Value`

- `zone_splits_at` (integer)
  - **Default:** `1`



### AccessLogsModel

- `bucket` (string) - Name of the bucket to store access logs.
  - **Default:** A dedicated bucket will be created.

- `enabled` (boolean)
  - **Default:** `True`

- `retain_days` (integer) - ELB access logs will be purged from S3 after this many days.
  - **Default:** `90`

- `prefix_expr` (string)
  - **Default:** `${AWS::StackName}-access.`



### ListenerModel

- `hostnames` (List of [HostnameModel](#HostnameModel)) - **Required for HTTPS listeners** - A list of hostnames this listener will answer to. This value is used for
                       certificate generation and DNS entry creation.

- `protocol` (string) - **required**

- `port` (integer) - **required**

- `https_redirect_to` (integer) - Shortcut for created an HTTPS redirect to the specified port.

- `rules` (List of [RuleModel](#RuleModel)) - Listener rules to direct requests beyond the default action.

- `default_action` ([ActionModel](#ActionModel)) - Default action for requests handled by this listener which do not match any other rules.
  - **Default:** If no `default_action` is specified then requests will be routed to an empty
                               target group. This may be useful in cases where
                               default traffic is handled by an ECS service.



#### ActionModel

An action may be a listener's `default_action` or it may be part of a
[RuleModel](#RuleModel). The default action when none of these properties
is specified is to create an empty target group. This may be useful in
cases where requests are handled by an ECS service.

- `fixed_response` ([FixedResponseModel](#FixedResponseModel)) - Provide a fixed response to all requests.
  - **See Also:** [AWS::ElasticLoadBalancingV2::ListenerRule FixedResponseConfig](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-elasticloadbalancingv2-listenerrule-fixedresponseconfig.html)

- `health_check` ([HealthCheckModel](#HealthCheckModel)) - Configures the behavior of the target group health check

- `redirect` ([RedirectModel](#RedirectModel)) - Specifies an HTTP 301 or 302 redirect

- `target_group_attributes` (Dict[string:string]) - Specifies target group attributes
  - The following attributes are defined by default but can be overriden:
    * `'stickiness.enabled' = 'true'`
    * `'stickiness.type' = 'lb_cookie'`
  - **See Also:** [AWS::ElasticLoadBalancingV2::TargetGroup TargetGroupAttribute](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-elasticloadbalancingv2-targetgroup-targetgroupattribute.html)

- `targets` (List of [TargetModel](#TargetModel)) - Members of the target group

- `target_port` (integer) - Default traffic port for members of the target group.
  - **Default:** `8080`
  - This value is overridden if a traffic port has been specified for the target.

- `target_protocol` (string) - Protocol for backend communication with the targets.
  - **Default:** `HTTP`



##### TargetModel

- `id` (string) - **required** - Instance ID of the target

- `port` (integer) - Traffic port of the target
  - **Default:** If `port` is not specified then the default `port` of the target group will be used.



##### RedirectModel

**See Also:** [AWS::ElasticLoadBalancingV2::ListenerRule RedirectConfig](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-elasticloadbalancingv2-listenerrule-redirectconfig.html)

- `host` (string)

- `path` (string) - The absolute path, starting with the leading "/"

- `port` (integer)

- `protocol` (string)
  - **Allowed Values:** `HTTP`, `HTTPS`, `#{protocol}`

- `query` (string) - The query parameters, URL-encoded when necessary, but not percent-encoded.

- `status_code` (integer)
  - **Default:** `302`
  - **Allowed Values:** `301` or `302`



##### HealthCheckModel

- `interval_seconds` (integer)
  - **Default:** The default value depends on the type of target group.
  - **See Also:** [AWS::ElasticLoadBalancingV2::TargetGroup](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-elasticloadbalancingv2-targetgroup.html#cfn-elasticloadbalancingv2-targetgroup-healthcheckintervalseconds)

- `path` (string) - Path the health check will query

- `timeout_seconds` (integer) - Timeout period for health check requests
  - **See Also:** [AWS::ElasticLoadBalancingV2::TargetGroup](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-elasticloadbalancingv2-targetgroup.html#cfn-elasticloadbalancingv2-targetgroup-healthchecktimeoutseconds)

- `protocol` (string)

- `healthy_threshold_count` (integer)

- `unhealth_threshold_count` (integer)



##### FixedResponseModel

**See Also:** [AWS::ElasticLoadBalancingV2::ListenerRule FixedResponseConfig](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-elasticloadbalancingv2-listenerrule-fixedresponseconfig.html)

- `message_body` (string)

- `content_type` (string)
  - **Default:** `text/plain`
  - **Allowed Values:** `text/plain`, `text/css`, `text/html`, `application/javascript`, `application/json`

- `status_code` (integer)
  - **Default:** `200`



#### RuleModel

A rule object is an [ActionModel](#ActionModel) with additional options to
specify a condition. At least one of these options must be specified.

- `fixed_response` ([FixedResponseModel](#FixedResponseModel)) - Provide a fixed response to all requests.
  - **See Also:** [AWS::ElasticLoadBalancingV2::ListenerRule FixedResponseConfig](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-elasticloadbalancingv2-listenerrule-fixedresponseconfig.html)

- `health_check` ([HealthCheckModel](#HealthCheckModel)) - Configures the behavior of the target group health check

- `redirect` ([RedirectModel](#RedirectModel)) - Specifies an HTTP 301 or 302 redirect

- `target_group_attributes` (Dict[string:string]) - Specifies target group attributes
  - The following attributes are defined by default but can be overriden:
    * `'stickiness.enabled' = 'true'`
    * `'stickiness.type' = 'lb_cookie'`
  - **See Also:** [AWS::ElasticLoadBalancingV2::TargetGroup TargetGroupAttribute](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-elasticloadbalancingv2-targetgroup-targetgroupattribute.html)

- `targets` (List of [TargetModel](#TargetModel)) - Members of the target group

- `target_port` (integer) - Default traffic port for members of the target group.
  - **Default:** `8080`
  - This value is overridden if a traffic port has been specified for the target.

- `target_protocol` (string) - Protocol for backend communication with the targets.
  - **Default:** `HTTP`

- `input_values` (Dict)

- `paths` (List of string) - Path or paths to match in the request

- `hosts` (List of string) - Hostnames to match in the requests host header

- `match_query_string` (List of [QueryStringMatchModel](#QueryStringMatchModel))

- `priority` (integer)



##### QueryStringMatchModel

- `key` (string) - **required**

- `value` (string) - **required**



#### HostnameModel

- `hostname` (string) - **required** - Short hostname or FQDN.
  - Hostnames which do not contain a dot (.) will be treated as "short" and the
               value specified in `domain` will be appended. If a short hostname
               is specified and `domain` has not been provided then an error
               will occur.

- `certificate_arn` (string) - ARN of the certificate to associate with this hostname
  - **Default:** If this value is not specified, then a certificate will be generated as part of the stack.
