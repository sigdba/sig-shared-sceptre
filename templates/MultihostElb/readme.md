# MultihostELB

Creates an Elastic Load Balancer and associated resources.

## Parameters

- `VpcId` (String) - **required** - The ID of the VPC where the ECS cluster will be created.



## sceptre_user_data

- `access_logs` ([AccessLogsModel](#AccessLogsModel))

- `allow_cidrs` (List of string) - A list of CIDRs allowed to access the ELB.
  - **Default:** With `allow_cidrs` empty, if `elb_security_groups` has been provided, then no
                               security group will be created. Otherwise, a new
                               SG will be created allowing all traffic.

- `alt_hosted_zone_ids` (List of string) - Additional Route53 hosted Zone IDs in which to create DNS entries. Will not
                       be used for certificate validation. This can be used, for
                       instance, to specify the internal size of a split-horizon
                       DNS setup.

- `attributes` (Dict[string:string]) - ELB attributes
  - Settings in `access_logs` will modify related ELB attributes.
  - **See Also:** [AWS::ElasticLoadBalancingV2::LoadBalancer](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-elasticloadbalancingv2-loadbalancer.html#cfn-elasticloadbalancingv2-loadbalancer-scheme)

- `certificate_validation_method` (string) - The method by which AWS Certificate Manager (ACM) will validate generated certificates.
  - **Default:** `DNS`
  - **Allowed Values:** `DNS`, `EMAIL`
  - If you do not wish the stack to generate certificates, then you must provide
               `certificate_arn` values for each `hostname` entry specified
               under `listeners`.

- `create_instance_sg` (boolean) - When True a security group will be created with a rule to
                       allow all traffic from the ELB. Instances can then be
                       assigned to this group as an alternative to using the
                       `sg_id` option on targets.
  - **Default:** `False`

- `domain` (string) - The domain to append to short hostnames used elsewhere in the template.
  - Any hostname specified in the configuration which does not contain a dot (.)
               will be treated as "short" and this value will be appended. If a
               short hostname is specified and `domain` has not been provided
               then an error will occur.

- `elb_security_groups` (List of string) - List if security group IDs to associate with the ELB.
  - If you specify this value and do not specify `allow_cidrs` then this stack will not create a security group.

- `elb_tags` (Dict[string:string]) - Tags to apply to the ELB object

- `elb_type` (string)
  - **Default:** `application`

- `hosted_zone_id` (string) - The Route53 hosted zone ID in which to create DNS entries for certificate
                       validation and for hostnames specified for
                       `listeners`.

- `internet_facing` (boolean) - **required** - If `true` the ELB will be created accessible externally, otherwise it will be
                       created as an "internal" ELB.
  - **See Also:** [AWS::ElasticLoadBalancingV2::LoadBalancer](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-elasticloadbalancingv2-loadbalancer.html#cfn-elasticloadbalancingv2-loadbalancer-scheme)

- `listeners` (List of [ListenerModel](#ListenerModel)) - **required** - One listener object for each port the ELB should listen on.

- `name` (string)
  - **Default:** `${AWS::StackName}`

- `ns_update` ([NsUpdateModel](#NsUpdateModel) or List of [NsUpdateModel](#NsUpdateModel)) - Specifies how DNS entries should be updated when not using Route53.

- `route53` ([Route53Model](#Route53Model)) - Extended options for Route53 records.
  - **Default:** `{'record_type': 'CNAME'}`

- `subnet_ids` (List of string) - At least two subnet IDs within the VPC for the ELB to occupy.

- `subnet_mappings` (List of Dict[string:string]) - The IDs of the public subnets. You can specify only one subnet per
                       Availability Zone. You must specify either subnets or
                       subnet mappings, but not both.
  - **See Also:** [AWS::ElasticLoadBalancingV2::LoadBalancer SubnetMapping](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-elasticloadbalancingv2-loadbalancer-subnetmapping.html)

- `waf_acls` (List of string or [WafAclModel](#WafAclModel)) - List of WAF WebACL ARNs and/or WafAclModel objects to associate with this ELB.



### Route53Model

- `record_type` (string) - Type of record to create in Route53.
  - **Allowed Values:** `CNAME`, `alias`
  - **Default:** `CNAME`



### WafAclModel

- `acl_tags` (Dict[string:string])

- `default_action` (string) - **required** - The action to perform if none of the Rules contained in the WebACL match.
  - **Allowed Values:** `allow`, `block`

- `description` (string)

- `metric_name` (string) - If defined, CloudWatch metrics for this ACL or rule will be enabled.

- `name` (string) - **required**

- `rules` (List of [WafAclRuleModel](#WafAclRuleModel)) - **required**

- `sample_requests_enabled` (boolean) - A boolean indicating whether AWS WAF should store a sampling of the web
                       requests that match the rules. You can view the sampled
                       requests through the AWS WAF console.
  - **Default:** `False`



#### WafAclRuleModel

- `action` (string)
  - **Allowed Values:** `allow`, `deny`

- `ip_set` (string or [WafIpSetModel](#WafIpSetModel)) - ARN of an IP set or a WafIpSetModel

- `managed_rule_set` ([WafManagedRulesetModel](#WafManagedRulesetModel))

- `metric_name` (string) - If defined, CloudWatch metrics for this ACL or rule will be enabled.

- `name` (string) - **required**

- `override_action` (string) - The override action to apply to the rules in a rule group, instead of the
                       individual rule action settings. This is used only for
                       rules whose statements reference a rule group.
  - **Allowed Values:** `count`, `none`
  - **Default:** =none=

- `priority` (integer) - AWS WAF processes rules with lower priority first.
  - **Default:** Rules without explicit priority values will be prioritized in the order they appear.
  - The priorities don't need to be consecutive, but they must all be different.
  - It is not recommended to mix rules with and without priorities specified.

- `regex_set` ([WafRegexSetModel](#WafRegexSetModel))

- `sample_requests_enabled` (boolean) - A boolean indicating whether AWS WAF should store a sampling of the web
                       requests that match the rules. You can view the sampled
                       requests through the AWS WAF console.
  - **Default:** `False`



##### WafManagedRulesetModel

- `excluded_rules` (List of string) - The rules whose actions are set to COUNT by the web ACL, regardless of the
                       action that is configured in the rule. This effectively
                       excludes the rule from acting on web requests.

- `name` (string) - **required**

- `vendor_name` (string) - **required**

- `version` (string)



##### WafRegexSetModel

- `arn` (string)

- `description` (string)

- `field_to_match` (string or Dict) - **required** - The part of a web request that you want AWS WAF to inspect. Refer to the
                       [FieldToMatch spec](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-wafv2-webacl-fieldtomatch.html)
                       for valid values. For fields which do not require
                       arguments (like UriPath) you can specify the field name
                       as a string.

- `name` (string)

- `regexes` (List of string)

- `text_transformations` (List of [WafTextTransformationModel](#WafTextTransformationModel))



###### WafTextTransformationModel

- `priority` (integer) - **required**

- `transform_type` (string) - **required** - See the [TextTransformation spec](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-wafv2-webacl-texttransformation.html) for valid values.



##### WafIpSetModel

- `addresses` (List of string) - **required**

- `description` (string)

- `ip_address_version` (string)
  - **Allowed Values:** `IPV4`, `IPV6`

- `name` (string) - **required**



### NsUpdateModel

- `lambda_arn` (string) - ARN of the Lambda function which provides NS update functionality.
  - One of `lambda_arn` or `lambda_arn_export_name` must be specified.

- `lambda_arn_export_name` (string) - Export name for the ARN of the Lambda function which provides NS update functionality.
  - One of `lambda_arn` or `lambda_arn_export_name` must be specified.

- `lambda_props` (Dict[string:string])

- `lambda_record_key` (string) - **required**

- `lambda_record_type_key` (string)
  - **Default:** `RecordType`

- `lambda_value_key` (string)
  - **Default:** `Value`

- `lambda_zone_key` (string) - **required**

- `zone_splits_at` (integer)
  - **Default:** `1`



### AccessLogsModel

- `bucket` (string) - Name of the bucket to store access logs.
  - **Default:** A dedicated bucket will be created.

- `enabled` (boolean)
  - **Default:** `True`

- `prefix_expr` (string)
  - **Default:** `${AWS::StackName}-access.`

- `retain_days` (integer) - ELB access logs will be purged from S3 after this many days.
  - **Default:** `90`



### ListenerModel

- `default_action` ([ActionModel](#ActionModel)) - Default action for requests handled by this listener which do not match any other rules.
  - **Default:** If no `default_action` is specified then requests will be routed to an empty
                               target group. This may be useful in cases where
                               default traffic is handled by an ECS service.

- `hostnames` (List of [HostnameModel](#HostnameModel)) - **Required for HTTPS listeners** - A list of hostnames this listener will answer to. This value is used for
                       certificate generation and DNS entry creation.

- `https_redirect_to` (integer) - Shortcut for created an HTTPS redirect to the specified port.

- `port` (integer) - **required**

- `protocol` (string) - **required**

- `rules` (List of [RuleModel](#RuleModel)) - Listener rules to direct requests beyond the default action.



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
  - The following attributes are defined by default on Application Load Balancers but can be overriden:
    * `'stickiness.enabled' = 'true'`
    * `'stickiness.type' = 'lb_cookie'`
  - **See Also:** [AWS::ElasticLoadBalancingV2::TargetGroup TargetGroupAttribute](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-elasticloadbalancingv2-targetgroup-targetgroupattribute.html)

- `target_port` (integer) - Default traffic port for members of the target group.
  - **Default:** `8080`
  - This value is overridden if a traffic port has been specified for the target.

- `target_protocol` (string) - Protocol for backend communication with the targets.
  - **Default:** `HTTP` for Application Load Balancers, `TCP` for Network Load Balancers

- `targets` (List of [TargetModel](#TargetModel)) - Members of the target group



##### TargetModel

- `id` (string) - Instance ID of the target

- `import_id` (string) - CloudFormation export name containing the instance ID of the target.

- `import_sg` (string) - CloudFormation export name containing the ID of target's security group. If provided, a rule will be added to allow the ELB access on `port`.

- `port` (integer) - Traffic port of the target
  - **Default:** If `port` is not specified then the default `port` of the target group will be used.

- `sg_id` (string) - ID of target's security group. If provided, a rule will be added to allow the ELB access on `port`.



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

- `healthy_threshold_count` (integer)

- `http_codes` (string) - A range or list of HTTP status codes which will be considered success.
  - **Default:** `200-399`
  - **See Also:** [AWS::ElasticLoadBalancingV2::TargetGroup Matcher](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-elasticloadbalancingv2-targetgroup-matcher.html#cfn-elasticloadbalancingv2-targetgroup-matcher-httpcode)

- `interval_seconds` (integer)
  - **Default:** The default value depends on the type of target group.
  - **See Also:** [AWS::ElasticLoadBalancingV2::TargetGroup](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-elasticloadbalancingv2-targetgroup.html#cfn-elasticloadbalancingv2-targetgroup-healthcheckintervalseconds)

- `path` (string) - Path the health check will query

- `protocol` (string)

- `timeout_seconds` (integer) - Timeout period for health check requests
  - **See Also:** [AWS::ElasticLoadBalancingV2::TargetGroup](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-elasticloadbalancingv2-targetgroup.html#cfn-elasticloadbalancingv2-targetgroup-healthchecktimeoutseconds)

- `unhealth_threshold_count` (integer)



##### FixedResponseModel

**See Also:** [AWS::ElasticLoadBalancingV2::ListenerRule FixedResponseConfig](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-elasticloadbalancingv2-listenerrule-fixedresponseconfig.html)

- `content_type` (string)
  - **Default:** `text/plain`
  - **Allowed Values:** `text/plain`, `text/css`, `text/html`, `application/javascript`, `application/json`

- `message_body` (string)

- `status_code` (integer)
  - **Default:** `200`



#### RuleModel

A rule object is an [ActionModel](#ActionModel) with additional options to
specify a condition. At least one of these options must be specified.

- `fixed_response` ([FixedResponseModel](#FixedResponseModel)) - Provide a fixed response to all requests.
  - **See Also:** [AWS::ElasticLoadBalancingV2::ListenerRule FixedResponseConfig](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-elasticloadbalancingv2-listenerrule-fixedresponseconfig.html)

- `health_check` ([HealthCheckModel](#HealthCheckModel)) - Configures the behavior of the target group health check

- `hosts` (List of string) - Hostnames to match in the requests host header

- `input_values` (Dict)

- `match_query_string` (List of [QueryStringMatchModel](#QueryStringMatchModel))

- `paths` (List of string) - Path or paths to match in the request

- `priority` (integer)

- `redirect` ([RedirectModel](#RedirectModel)) - Specifies an HTTP 301 or 302 redirect

- `target_group_attributes` (Dict[string:string]) - Specifies target group attributes
  - The following attributes are defined by default on Application Load Balancers but can be overriden:
    * `'stickiness.enabled' = 'true'`
    * `'stickiness.type' = 'lb_cookie'`
  - **See Also:** [AWS::ElasticLoadBalancingV2::TargetGroup TargetGroupAttribute](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-elasticloadbalancingv2-targetgroup-targetgroupattribute.html)

- `target_port` (integer) - Default traffic port for members of the target group.
  - **Default:** `8080`
  - This value is overridden if a traffic port has been specified for the target.

- `target_protocol` (string) - Protocol for backend communication with the targets.
  - **Default:** `HTTP` for Application Load Balancers, `TCP` for Network Load Balancers

- `targets` (List of [TargetModel](#TargetModel)) - Members of the target group



##### QueryStringMatchModel

- `key` (string) - **required**

- `value` (string) - **required**



#### HostnameModel

- `certificate_arn` (string) - ARN of the certificate to associate with this hostname
  - **Default:** If this value is not specified, then a certificate will be generated as part of the stack.

- `certificate_validation_method` (string) - The method by which AWS Certificate Manager (ACM) will
                       validate generated certificates. Overrides
                       `sceptre_user_data.certificate_validation_method`.
  - **Allowed Values:** `DNS`, `EMAIL`

- `hosted_zone_id` (string or List of string) - ID or list of IDs for the Route53 hosted zones in which to register this hostname.
  - **Default:** If this value is not specified, then the value(s)
                               from `sceptre_user_data.hosted_zone_id` and
                               `sceptre_user_data.alt_hosted_zone_ids` will be
                               used.

- `hostname` (string) - **required** - Short hostname or FQDN.
  - Hostnames which do not contain a dot (.) will be treated as "short" and the
               value specified in `domain` will be appended. If a short hostname
               is specified and `domain` has not been provided then an error
               will occur.

