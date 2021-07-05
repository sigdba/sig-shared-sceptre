# MultiHostElb.py - ELB With Support for Multiple Hostnames using Listener Rules

## Parameters
* `VpcId` (string) - *Required* - The ID of the VPC where the ECS cluster will be created.

## sceptre_user_data

* `domain`
* `internet_facing`
* `listeners`
* `subnet_ids`

* `access_log_retain_days` (integer)
  * **Default:** `90`
* `allow_cidrs`  
  * **Default:** If `elb_security_groups` has been provided, then no security group will be created. Otherwise, a new
    SG will be created allowing all traffic.
* `attributes`
* `certificate_validation_method`  
  * **Default:** `DNS`
  * **Allowed Values:** `DNS`, `EMAIL`
* `elb_security_groups`
* `elb_tags`
* `hosted_zone_id`

## listener objects

* `port`

* `default_action`
* `https_redirect_to`
* `hostnames` 

### action objects

* `fixed_response`
* `health_check`
  
* `target_port` (integer)
  * **Default:** `8080`
  * **Note:** This value is overridden if a traffic port has been specified for the target.
  
* `target_protocol` (string)
  * **Default:** `HTTP`
  
* `target_group_attributes` - (string:string dictionary) - Sets target group attributes
  * **Defaults:** The following attributes are defined by default:
    * `'stickiness.enabled' = 'true'`
    * `'stickiness.type' = 'lb_cookie'`
  * **See Also:** [AWS::ElasticLoadBalancingV2::TargetGroup TargetGroupAttribute](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-elasticloadbalancingv2-targetgroup-targetgroupattribute.html)
  
* `targets` (list of strings or target objects)
  

#### fixed response objects

* `message_body`
  
* `content_type`
  * **Default:** `text/plain`
  
* `status_code`
  * **Default:** `200`
  
#### health check objects

* `interval_seconds`
  * **Default:** The default value depends on the type of target group. 
  * **See Also:** [AWS::ElasticLoadBalancingV2::TargetGroup](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-elasticloadbalancingv2-targetgroup.html#cfn-elasticloadbalancingv2-targetgroup-healthcheckintervalseconds)
  
* `path`
    
* `timeout_seconds` (integer) - 
  * **Default:** The default value depends on the type of target group.
  * **See Also:** [AWS::ElasticLoadBalancingV2::TargetGroup](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-elasticloadbalancingv2-targetgroup.html#cfn-elasticloadbalancingv2-targetgroup-healthchecktimeoutseconds)
  
#### target objects

* `id`
* `port`

### hostname objects

* `hostname`
* `certificate_arn`