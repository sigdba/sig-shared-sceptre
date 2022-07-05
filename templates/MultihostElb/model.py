from typing import Dict, List, Literal, Optional, Union

from pydantic import Field, constr, root_validator, validator

from util import (
    BaseModel,
    model_alias,
    model_exclusive,
    model_limit_values,
    model_string_or_list,
)

#
# IMPORTANT: The following classes are DATA CLASSES using pydantic.
#            DO NOT add behavior to them beyond input validation. Use functions
#            instead.
#


class RetainInputsModel(BaseModel):
    input_values = {}

    @root_validator(pre=True)
    def store_input_values(cls, values):
        return {**values, "input_values": values}


class HostnameModel(BaseModel):
    hostname: str = Field(
        description="Short hostname or FQDN.",
        notes=[
            """Hostnames which do not contain a dot (.) will be treated as "short" and the
               value specified in `domain` will be appended. If a short hostname
               is specified and `domain` has not been provided then an error
               will occur."""
        ],
    )
    certificate_arn: Optional[str] = Field(
        description="ARN of the certificate to associate with this hostname",
        default_description="If this value is not specified, then a certificate will be generated as part of the stack.",
    )
    hosted_zone_id: Optional[Union[str, List[str]]] = Field(
        description="ID or list of IDs for the Route53 hosted zones in which to register this hostname.",
        default_description="""If this value is not specified, then the value(s)
                               from `sceptre_user_data.hosted_zone_id` and
                               `sceptre_user_data.alt_hosted_zone_ids` will be
                               used.""",
    )
    certificate_validation_method: Optional[str] = Field(
        description="""The method by which AWS Certificate Manager (ACM) will
                       validate generated certificates. Overrides
                       `sceptre_user_data.certificate_validation_method`.""",
        notes=[
            "**Allowed Values:** `DNS`, `EMAIL`",
        ],
    )

    @root_validator
    def hosted_zone_ids_to_list(cls, values):
        return model_string_or_list("hosted_zone_id", values)


class RedirectModel(BaseModel):
    """**See Also:** [AWS::ElasticLoadBalancingV2::ListenerRule RedirectConfig](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-elasticloadbalancingv2-listenerrule-redirectconfig.html)"""

    host: Optional[str]
    path: Optional[str] = Field(
        description='The absolute path, starting with the leading "/"'
    )
    port: Optional[int]
    protocol: Optional[str] = Field(
        notes=["**Allowed Values:** `HTTP`, `HTTPS`, `#{protocol}`"]
    )
    query: Optional[str] = Field(
        description="The query parameters, URL-encoded when necessary, but not percent-encoded."
    )
    status_code = Field(302, notes=["**Allowed Values:** `301` or `302`"])

    @validator("protocol")
    def check_protocol(cls, v):
        return model_limit_values(["HTTP", "HTTPS", "#{protocol}"], v)

    @validator("status_code")
    def check_status_code(cls, v):
        return model_limit_values([301, 302], v)


class TargetModel(BaseModel):
    id: Optional[str] = Field(description="Instance ID of the target")
    import_id: Optional[str] = Field(
        description="CloudFormation export name containing the instance ID of the target."
    )
    sg_id: Optional[str] = Field(
        description="ID of target's security group. If provided, a rule will be added to allow the ELB access on `port`."
    )
    import_sg: Optional[str] = Field(
        description="CloudFormation export name containing the ID of target's security group. If provided, a rule will be added to allow the ELB access on `port`."
    )
    port: Optional[int] = Field(
        description="Traffic port of the target",
        default_description="If `port` is not specified then the default `port` of the target group will be used.",
    )

    @root_validator(pre=True)
    def check_exclusives(cls, values):
        model_exclusive(values, "id", "import_id", required=True)
        model_exclusive(values, "sg_id", "import_sg")
        return values


class HealthCheckModel(BaseModel):
    interval_seconds: Optional[int] = Field(
        default_description="The default value depends on the type of target group.",
        notes=[
            "**See Also:** [AWS::ElasticLoadBalancingV2::TargetGroup](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-elasticloadbalancingv2-targetgroup.html#cfn-elasticloadbalancingv2-targetgroup-healthcheckintervalseconds)"
        ],
    )
    path: Optional[str] = Field(description="Path the health check will query")
    timeout_seconds: Optional[int] = Field(
        description="Timeout period for health check requests",
        notes=[
            "**See Also:** [AWS::ElasticLoadBalancingV2::TargetGroup](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-elasticloadbalancingv2-targetgroup.html#cfn-elasticloadbalancingv2-targetgroup-healthchecktimeoutseconds)"
        ],
    )
    interval_seconds: Optional[int]
    protocol: Optional[str]
    healthy_threshold_count: Optional[int]
    unhealth_threshold_count: Optional[int]


class FixedResponseModel(BaseModel):
    """**See Also:** [AWS::ElasticLoadBalancingV2::ListenerRule FixedResponseConfig](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-elasticloadbalancingv2-listenerrule-fixedresponseconfig.html)"""

    message_body: Optional[str]
    content_type = Field(
        "text/plain",
        notes=[
            "**Allowed Values:** `text/plain`, `text/css`, `text/html`, `application/javascript`, `application/json`"
        ],
    )
    status_code = 200

    @validator("content_type")
    def check_content_type(cls, v):
        return model_limit_values(
            [
                "text/plain",
                "text/css",
                "text/html",
                "application/javascript",
                "application/json",
            ],
            v,
        )


class ActionModel(BaseModel):
    """An action may be a listener's `default_action` or it may be part of a
    [RuleModel](#RuleModel). The default action when none of these properties
    is specified is to create an empty target group. This may be useful in
    cases where requests are handled by an ECS service."""

    fixed_response: Optional[FixedResponseModel] = Field(
        description="Provide a fixed response to all requests.",
        notes=[
            "**See Also:** [AWS::ElasticLoadBalancingV2::ListenerRule FixedResponseConfig](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-elasticloadbalancingv2-listenerrule-fixedresponseconfig.html)"
        ],
    )
    health_check: Optional[HealthCheckModel] = Field(
        description="Configures the behavior of the target group health check"
    )
    redirect: Optional[RedirectModel] = Field(
        description="Specifies an HTTP 301 or 302 redirect"
    )
    target_port = Field(
        8080,
        description="Default traffic port for members of the target group.",
        notes=[
            "This value is overridden if a traffic port has been specified for the target."
        ],
    )
    target_protocol: Optional[str] = Field(
        description="Protocol for backend communication with the targets.",
        default_description="`HTTP` for Application Load Balancers, `TCP` for Network Load Balancers",
    )
    target_group_attributes: Dict[str, str] = Field(
        {},
        description="Specifies target group attributes",
        notes=[
            """The following attributes are defined by default on Application Load Balancers but can be overriden:
    * `'stickiness.enabled' = 'true'`
    * `'stickiness.type' = 'lb_cookie'`""",
            "**See Also:** [AWS::ElasticLoadBalancingV2::TargetGroup TargetGroupAttribute](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-elasticloadbalancingv2-targetgroup-targetgroupattribute.html)",
        ],
    )
    targets: List[TargetModel] = Field([], description="Members of the target group")

    @validator("targets", pre=True, each_item=True)
    def coerce_targets(cls, v):
        if isinstance(v, str):
            return TargetModel(id=v)
        return v


class QueryStringMatchModel(BaseModel):
    key: str
    value: str


class RuleModel(RetainInputsModel, ActionModel):
    """A rule object is an [ActionModel](#ActionModel) with additional options to
    specify a condition. At least one of these options must be specified."""

    paths: List[str] = Field([], description="Path or paths to match in the request")
    hosts: List[str] = Field(
        [], description="Hostnames to match in the requests host header"
    )
    match_query_string: List[QueryStringMatchModel] = []
    priority: Optional[int]
    # TODO: Document priority
    # TODO: Use Pydantic aliases

    @root_validator(pre=True)
    def path_alias(cls, values):
        return model_string_or_list("paths", model_alias("paths", "path", values))

    @root_validator(pre=True)
    def host_alias(cls, values):
        return model_string_or_list("hosts", model_alias("hosts", "host", values))

    @root_validator()
    def require_hosts_or_paths(cls, values):
        if len(values["hosts"]) < 1 and len(values["paths"]) < 1:
            raise ValueError("one of hosts or paths must be specified")
        return values


class ListenerModel(BaseModel):
    hostnames: List[HostnameModel] = Field(
        [],
        description="""A list of hostnames this listener will answer to. This value is used for
                       certificate generation and DNS entry creation.""",
        requirement_description="Required for HTTPS listeners",
    )
    protocol: constr(regex="[A-Z_]+")
    port: int
    default_action = Field(
        ActionModel(),
        description="Default action for requests handled by this listener which do not match any other rules.",
        default_description="""If no `default_action` is specified then requests will be routed to an empty
                               target group. This may be useful in cases where
                               default traffic is handled by an ECS service.""",
    )
    https_redirect_to: Optional[int] = Field(
        description="Shortcut for created an HTTPS redirect to the specified port."
    )
    rules: List[RuleModel] = Field(
        [], description="Listener rules to direct requests beyond the default action."
    )

    @root_validator(pre=True)
    def detect_protocol(cls, values):
        if "protocol" not in values:
            port = values["port"]
            if port == 80:
                values["protocol"] = "HTTP"
            elif port == 443:
                values["protocol"] = "HTTPS"
            else:
                raise ValueError(
                    "You must specify a protocol for listener on non-standard port: {}".format(
                        port
                    )
                )
        return values

    @validator("hostnames", pre=True, each_item=True)
    def coerce_hostnames(cls, v):
        if isinstance(v, str):
            return HostnameModel(hostname=v)
        return v

    @root_validator
    def require_hostnames_for_https(cls, values):
        if "protocol" not in values:
            # We're already in an error state. Don't do further checking.
            return values
        if values["protocol"] == "HTTPS" and (
            "hostnames" not in values or len(values["hostnames"]) < 1
        ):
            raise ValueError("hostnames key is required for HTTPS listeners")
        return values


class NsUpdateModel(BaseModel):
    lambda_arn: Optional[str] = Field(
        description="ARN of the Lambda function which provides NS update functionality.",
        notes=["One of `lambda_arn` or `lambda_arn_export_name` must be specified."],
    )
    lambda_arn_export_name: Optional[str] = Field(
        description="Export name for the ARN of the Lambda function which provides NS update functionality.",
        notes=["One of `lambda_arn` or `lambda_arn_export_name` must be specified."],
    )
    lambda_props: Dict[str, str] = {}
    lambda_record_type_key = "RecordType"
    lambda_record_key: str
    lambda_zone_key: str
    lambda_value_key = "Value"
    zone_splits_at = 1

    @root_validator()
    def require_lambda_arn_or_export(cls, values):
        if "lambda_arn" not in values and "lambda_arn_export_name" not in values:
            raise ValueError(
                "one of lambda_arn or lambda_arn_export_name must be specified"
            )
        return values


class AccessLogsModel(BaseModel):
    enabled = True
    retain_days = Field(
        90, description="ELB access logs will be purged from S3 after this many days."
    )
    prefix_expr = "${AWS::StackName}-access."
    bucket: Optional[str] = Field(
        description="Name of the bucket to store access logs.",
        default_description="A dedicated bucket will be created.",
    )


class HasWafVisibility(BaseModel):
    metric_name: Optional[str] = Field(
        description="If defined, CloudWatch metrics for this ACL or rule will be enabled."
    )
    sample_requests_enabled = Field(
        False,
        description="""A boolean indicating whether AWS WAF should store a sampling of the web
                       requests that match the rules. You can view the sampled
                       requests through the AWS WAF console.""",
    )


class WafIpSetModel(BaseModel):
    name: str
    description: Optional[str]
    addresses: List[str]
    ip_address_version: Optional[Literal["IPV4", "IPV6"]]

    @root_validator(pre=True)
    def detect_address_version(cls, values):
        if "ip_address_version" in values:
            return values
        addrs = values["addresses"]

        def check(s):
            return any(filter(lambda a: s in a, addrs))

        has4 = check(".")
        has6 = check(":")
        if has4 and has6:
            raise ValueError("addresses cannot contain both IPv4 and IPv6 entries")
        values["ip_address_version"] = "IPV6" if has6 else "IPV4"
        return values


class WafTextTransformationModel(BaseModel):
    priority: int
    transform_type: str = Field(
        description="See the [TextTransformation spec](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-wafv2-webacl-texttransformation.html) for valid values."
    )


class WafRegexSetModel(BaseModel):
    arn: Optional[str]
    name: Optional[str]
    description: Optional[str]
    regexes: Optional[List[str]]
    field_to_match: Union[str, dict] = Field(
        description="""The part of a web request that you want AWS WAF to inspect. Refer to the
                       [FieldToMatch spec](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-wafv2-webacl-fieldtomatch.html)
                       for valid values. For fields which do not require
                       arguments (like UriPath) you can specify the field name
                       as a string."""
    )
    text_transformations: List[WafTextTransformationModel] = []

    @root_validator
    def ref_or_new(cls, values):
        kind = model_exclusive(values, "arn", "regexes", required=True)
        if kind == "regexes" and not values.get("name"):
            raise ValueError("name is required when building a new RegexPatternSet")
        return values


class WafManagedRulesetModel(BaseModel):
    name: str
    vendor_name: str
    version: Optional[str]
    excluded_rules: List[str] = Field(
        [],
        description="""The rules whose actions are set to COUNT by the web ACL, regardless of the
                       action that is configured in the rule. This effectively
                       excludes the rule from acting on web requests.""",
    )


class WafAclRuleModel(HasWafVisibility):
    name: str
    action: Optional[Literal["allow", "deny"]]
    override_action: Optional[Literal["count", "none"]] = Field(
        description="""The override action to apply to the rules in a rule group, instead of the
                       individual rule action settings. This is used only for
                       rules whose statements reference a rule group.""",
        default_description="=none=",
    )
    priority: Optional[int] = Field(
        description="AWS WAF processes rules with lower priority first.",
        default_description="Rules without explicit priority values will be prioritized in the order they appear.",
        notes=[
            "The priorities don't need to be consecutive, but they must all be different.",
            "It is not recommended to mix rules with and without priorities specified.",
        ],
    )
    ip_set: Optional[Union[str, WafIpSetModel]] = Field(
        description="ARN of an IP set or a WafIpSetModel"
    )
    regex_set: Optional[WafRegexSetModel]
    managed_rule_set: Optional[WafManagedRulesetModel]

    @root_validator
    def exclusive_statements(cls, values):
        model_exclusive(
            values, "ip_set", "regex_set", "managed_rule_set", required=True
        )

        return values

    @root_validator
    def require_action(cls, values):
        if not values.get("managed_rule_set") and not values.get("action"):
            raise ValueError("action is required except when using managed_rule_set")
        return values

    @root_validator(pre=True)
    def override_action_default(cls, values):
        if values.get("managed_rule_set") and not values.get("override_action"):
            values["override_action"] = "none"
        return values


class WafAclModel(HasWafVisibility):
    name: str
    description: Optional[str]
    default_action: Literal["allow", "block"] = Field(
        description="The action to perform if none of the Rules contained in the WebACL match."
    )
    rules: List[WafAclRuleModel]
    acl_tags: Dict[str, str] = {}

    @root_validator
    def generate_rule_priorities(cls, values):
        if "rules" not in values:
            # Rules must have failed validation
            return values

        p = 200
        for r in values["rules"]:
            if r.priority:
                p = r.priority + 100
            else:
                r.priority = p
                p = p + 10
        return values


class UserDataModel(BaseModel):
    name = "${AWS::StackName}"
    listeners: List[ListenerModel] = Field(
        description="One listener object for each port the ELB should listen on."
    )
    subnet_ids: Optional[List[str]] = Field(
        description="At least two subnet IDs within the VPC for the ELB to occupy."
    )
    subnet_mappings: Optional[List[Dict[str, str]]] = Field(
        description="""The IDs of the public subnets. You can specify only one subnet per
                       Availability Zone. You must specify either subnets or
                       subnet mappings, but not both.""",
        notes=[
            "**See Also:** [AWS::ElasticLoadBalancingV2::LoadBalancer SubnetMapping](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-elasticloadbalancingv2-loadbalancer-subnetmapping.html)"
        ],
    )
    domain: Optional[str] = Field(
        description="The domain to append to short hostnames used elsewhere in the template.",
        notes=[
            """Any hostname specified in the configuration which does not contain a dot (.)
               will be treated as "short" and this value will be appended. If a
               short hostname is specified and `domain` has not been provided
               then an error will occur."""
        ],
    )
    elb_type = "application"
    internet_facing: bool = Field(
        description="""If `true` the ELB will be created accessible externally, otherwise it will be
                       created as an "internal" ELB.""",
        notes=[
            "**See Also:** [AWS::ElasticLoadBalancingV2::LoadBalancer](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-elasticloadbalancingv2-loadbalancer.html#cfn-elasticloadbalancingv2-loadbalancer-scheme)"
        ],
    )
    access_logs: Optional[AccessLogsModel]
    allow_cidrs: Optional[List[str]] = Field(
        description="A list of CIDRs allowed to access the ELB.",
        default_description="""With `allow_cidrs` empty, if `elb_security_groups` has been provided, then no
                               security group will be created. Otherwise, a new
                               SG will be created allowing all traffic.""",
    )
    attributes: Dict[str, str] = Field(
        {},
        description="ELB attributes",
        notes=[
            "Settings in `access_logs` will modify related ELB attributes.",
            "**See Also:** [AWS::ElasticLoadBalancingV2::LoadBalancer](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-elasticloadbalancingv2-loadbalancer.html#cfn-elasticloadbalancingv2-loadbalancer-scheme)",
        ],
    )
    certificate_validation_method = Field(
        "DNS",
        description="""The method by which AWS Certificate Manager (ACM) will validate generated certificates.""",
        notes=[
            "**Allowed Values:** `DNS`, `EMAIL`",
            """If you do not wish the stack to generate certificates, then you must provide
               `certificate_arn` values for each `hostname` entry specified
               under `listeners`.""",
        ],
    )
    elb_security_groups: List[str] = Field(
        [],
        description="List if security group IDs to associate with the ELB.",
        notes=[
            "If you specify this value and do not specify `allow_cidrs` then this stack will not create a security group."
        ],
    )
    elb_tags: Dict[str, str] = Field({}, description="Tags to apply to the ELB object")
    hosted_zone_id: Optional[str] = Field(
        description="""The Route53 hosted zone ID in which to create DNS entries for certificate
                       validation and for hostnames specified for
                       `listeners`."""
    )
    alt_hosted_zone_ids: List[str] = Field(
        [],
        description="""Additional Route53 hosted Zone IDs in which to create DNS entries. Will not
                       be used for certificate validation. This can be used, for
                       instance, to specify the internal size of a split-horizon
                       DNS setup.""",
    )
    ns_update: Optional[Union[NsUpdateModel, List[NsUpdateModel]]] = Field(
        description="Specifies how DNS entries should be updated when not using Route53."
    )
    waf_acls: List[Union[str, WafAclModel]] = Field(
        [],
        description="List of WAF WebACL ARNs and/or WafAclModel objects to associate with this ELB.",
    )

    @validator("ns_update")
    def ns_update_force_list(cls, v):
        if type(v) is list:
            return v
        return [v]

    @validator("listeners")
    def require_listeners(cls, v):
        if not v or len(v) < 1:
            raise ValueError("at least one listener is required")
        return v

    @root_validator
    def require_subnets(cls, values):
        model_exclusive(values, "subnet_ids", "subnet_mappings", required=True)
        return values

    # TODO: Add error if security groups are specified for network LBs
