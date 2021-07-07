# MultiHostElb.py - ELB With Support for Multiple Hostnames using Listener Rules

## Parameters
* `VpcId` (string) - *Required* - The ID of the VPC where the ECS cluster will be created.


## sceptre_user_data

* `listeners` (list of [listener objects](#listener-objects)) - *Required* - One listener object for each port the ELB
  should listen on.

* `subnet_ids` (list of strings) - *Required* - At least two subnet IDs within the VPC for the ELB to occupy.
  
* `domain` (string) - The domain to append to short hostnames used elsewhere in the template.
  * **Note**: Any hostname specified in the configuration which does not contain a dot (.) will be treated as "short"
    and this value will be appended. If a short hostname is specified and `domain` has not been provided then an error
    will occur.
    
* `internet_facing` (boolean) - If `true` the ELB will be created accessible externally, otherwise it will be created
  as an "internal" ELB.
  * **See Also:** [AWS::ElasticLoadBalancingV2::LoadBalancer](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-elasticloadbalancingv2-loadbalancer.html#cfn-elasticloadbalancingv2-loadbalancer-scheme)

* `access_log_retain_days` (integer) - ELB access logs will be purged from S3 after this many days.
  * **Default:** `90`
  * **Note:** If the `access_logs.s3.enabled` load-balancer attribute has been set to `false` then this value will have
    no effect.
  
* `allow_cidrs` (list of strings) - A list of CIDRs allowed to access the ELB.
  * **Default:** If `elb_security_groups` has been provided, then no security group will be created. Otherwise, a new
    SG will be created allowing all traffic.
    
* `attributes` (string:string dict) - ELB attributes 
  * **Defaults:** The following defaults are provided:
    * `access_logs.s3.enabled = true`
    * `access_logs.s3.prefix = ${AWS::StackName}-access.`  
  * **See Also:** [AWS::ElasticLoadBalancingV2::LoadBalancer](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-elasticloadbalancingv2-loadbalancer.html#cfn-elasticloadbalancingv2-loadbalancer-scheme)
  
* `certificate_validation_method` (string) - The method by which AWS Certificate Manager (ACM) will validate
  generated certificates.
  * **Default:** `DNS`
  * **Allowed Values:** `DNS`, `EMAIL`
  * **Note:** If you do not wish the stack to generate certificates, then you must provide `certificate_arn` values for
    each `hostname` entry specified under `listeners`. 
  
* `elb_security_groups` (list of strings) - List if security group IDs to associate with the ELB.
  * **Note:** If you specify this value and do not specify `allow_cidrs` then this stack will not create a security
    group.
    
* `elb_tags` (string:string dict) - Tags to apply to the ELB object
  
* `hosted_zone_id` (string) - The Route53 hosted zone ID in which to create DNS entries for certificate validation and
  for hostnames specified for `listeners`.
  

### listener objects

* `hostnames` (list of strings and/or [hostname objects](#hostname-objects)) - *Required for HTTPS listeners* - A list
  of hostnames this listener will answer to. This value is used for certificate generation and DNS entry creation.
  
* `port` (integer) - *Required* - Port for this listener to listen on

* `default_action` ([action object](#action-objects)) - Default action for requests handled by this listener which do
  not match any other rules.
  * **Default:** If no `default_action` is specified then requests will be routed to an empty target group. This may be
    useful in cases where default traffic is handled by an ECS service.
  
* `https_redirect_to` (integer) - Shortcut for created an HTTPS redirect to the specified port.
  
* `rules` (list of rule objects) - Listener rules to direct requests beyond the default action.


#### action objects

An action may be a listener's `default_action` or it may be part of a [rule object](#rule-objects). The default action
when none of these properties is specified is to create an empty target group. This may be useful in cases where
requests are handled by an ECS service.

* `fixed_response` ([fixed response object](#fixed-response-objects)) - Provide a fixed response to all requests.
  * **See Also:** [AWS::ElasticLoadBalancingV2::ListenerRule FixedResponseConfig](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-elasticloadbalancingv2-listenerrule-fixedresponseconfig.html)
  
* `health_check` ([health check object](#health-check-objects)) - Configures the behavior of the target group health 
  check
  * **Default:** The default health check will query the path provided by the rule (or `/` for `default_action` and
    rules without `paths` specified) and will consider responses `200`-`399` healthy.

* `redirect` (redirect object) - Specifies an HTTP 301 or 302 redirect
  
* `target_port` (integer) - Default traffic port for members of the target group.
  * **Default:** `8080`
  * **Note:** This value is overridden if a traffic port has been specified for the target.
  
* `target_protocol` (string) - Protocol for backend communication with the targets.
  * **Default:** `HTTP`
  * **Allowed Values:** `HTTP` or `HTTPS`
  
* `target_group_attributes` - (string:string dictionary) - Specifies target group attributes
  * **Defaults:** The following attributes are defined by default:
    * `'stickiness.enabled' = 'true'`
    * `'stickiness.type' = 'lb_cookie'`
  * **See Also:** [AWS::ElasticLoadBalancingV2::TargetGroup TargetGroupAttribute](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-elasticloadbalancingv2-targetgroup-targetgroupattribute.html)
  
* `targets` (list of strings or [target objects](#target-objects)) - Members of the target group


##### fixed response objects

**See Also:** [AWS::ElasticLoadBalancingV2::ListenerRule FixedResponseConfig](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-elasticloadbalancingv2-listenerrule-fixedresponseconfig.html)

* `message_body` (string) - The message
  
* `content_type` (string) - MIME content type
  * **Default:** `text/plain`
  * **Allowed Values:** `text/plain`, `text/css`, `text/html`, `application/javascript`, `application/json`
  
* `status_code` (integer) - HTTP response code
  * **Default:** `200`
  
##### health check objects

* `interval_seconds` (integer) - Seconds between health checks
  * **Default:** The default value depends on the type of target group. 
  * **See Also:** [AWS::ElasticLoadBalancingV2::TargetGroup](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-elasticloadbalancingv2-targetgroup.html#cfn-elasticloadbalancingv2-targetgroup-healthcheckintervalseconds)
  
* `path` (string) - Path to query
    
* `timeout_seconds` (integer) - Timeout period for health check requests
  * **Default:** The default value depends on the type of target group.
  * **See Also:** [AWS::ElasticLoadBalancingV2::TargetGroup](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-elasticloadbalancingv2-targetgroup.html#cfn-elasticloadbalancingv2-targetgroup-healthchecktimeoutseconds)
  
##### target objects

* `id` (string) - *Required* - Instance ID of the target
* `port` (integer) - Traffic port of the target
  * **Default:** If `port` is not specified then the default `port` of the target group will be used.

##### redirect objects

**See Also:** [AWS::ElasticLoadBalancingV2::ListenerRule RedirectConfig](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-elasticloadbalancingv2-listenerrule-redirectconfig.html)

* `host` (string) - The hostname
  
* `path` (string) - The absolute path, starting with the leading "/"
  
* `port` (integer) - The port
  
* `protocol` (string) - The protocol
  * **Allowed Values:** `HTTP`, `HTTPS`, `#{protocol}`
  
* `query` (string) - The query parameters, URL-encoded when necessary, but not percent-encoded. 
  
* `status_code` (integer) - The HTTP redirect code
  * **Default:** `302`
  * **Allowed Values:** `301` or `302`

#### rule objects

A rule object is an [action object](#action-objects) with the following options to specify a condition. At least one of
these options must be specified.

* `path` (string or list of strings) - Alias for `paths`
  
* `paths` (string or list of strings) - Path or paths to match in the request
  
* `host` (string or list of strings) - Alias for `hosts`  
  
* `hosts` (string or list of strings) - Hostnames to match in the requests host header

#### hostname objects

* `hostname` (string) - Short hostname or FQDN.
   * **Note**: Hostnames which do not contain a dot (.) will be treated as "short" and the value specified in `domain` 
     will be appended. If a short hostname is specified and `domain` has not been provided then an error will occur.
  
* `certificate_arn` (string) - ARN of the certificate to associate with this hostname
  * **Default:** If this value is not specified, then a certificate will be generated as part of the stack.
    