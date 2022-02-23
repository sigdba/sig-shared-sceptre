from functools import lru_cache, partial

from troposphere import Ref, Sub, Parameter, GetAtt, Tag, ImportValue, Tags
from troposphere.cloudformation import AWSCustomObject
from troposphere.elasticloadbalancingv2 import (
    Action,
    Certificate as ListenerCertificateEntry,
    Condition,
    FixedResponseConfig,
    ForwardConfig,
    HostHeaderConfig,
    Listener,
    ListenerCertificate,
    ListenerRule,
    LoadBalancer,
    LoadBalancerAttributes,
    Matcher,
    PathPatternConfig,
    QueryStringConfig,
    QueryStringKeyValue,
    RedirectConfig,
    SubnetMapping,
    TargetDescription,
    TargetGroup,
    TargetGroupAttribute,
)
from troposphere.s3 import (
    Bucket,
    BucketPolicy,
    LifecycleConfiguration,
    LifecycleRule,
    LifecycleRuleTransition,
    PublicAccessBlockConfiguration,
)
from troposphere.certificatemanager import Certificate, DomainValidationOption
from troposphere.route53 import RecordSet, RecordSetType
from troposphere.ec2 import SecurityGroup, SecurityGroupIngress, SecurityGroupRule
from troposphere.wafv2 import (
    IPSet,
    RegexPatternSet,
    IPSetReferenceStatement,
    ExcludedRule,
    ManagedRuleGroupStatement,
    RegexPatternSetReferenceStatement,
    RuleGroupReferenceStatement,
    VisibilityConfig,
    RuleGroupRule,
    RuleGroup,
    DefaultAction,
    OverrideAction,
    WebACLRule,
    WebACL,
    WebACLAssociation,
    FieldToMatch,
    TextTransformation,
    StatementOne as WafStatement,
    RuleAction,
)

from model import *
from util import *

import troposphere.wafv2

PRIORITY_CACHE = []


def priority_hash(s, range_start=1000, range_end=47999):
    ret = int(md5(s), 16) % (range_end - range_start) + range_start
    while ret in PRIORITY_CACHE:
        ret += 1
    PRIORITY_CACHE.append(ret)
    return ret


def hostname_to_fqdn(user_data, hostname):
    return hostname if "." in hostname else "{}.{}".format(hostname, user_data.domain)


def camel_case(s):
    return "".join(map(str.title, s.split("_")))


def log_bucket(user_data):
    return add_resource(
        Bucket(
            "LogBucket",
            LifecycleConfiguration=LifecycleConfiguration(
                Rules=[
                    LifecycleRule(
                        ExpirationInDays=user_data.access_logs.retain_days,
                        Status="Enabled",
                    )
                ]
            ),
            PublicAccessBlockConfiguration=PublicAccessBlockConfiguration(
                BlockPublicAcls=True,
                BlockPublicPolicy=True,
                IgnorePublicAcls=True,
                RestrictPublicBuckets=True,
            ),
        )
    )


def log_bucket_policy():
    return add_resource(
        BucketPolicy(
            "LogBucketPolicy",
            Bucket=Ref("LogBucket"),
            PolicyDocument={
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {
                            "AWS": {
                                "Fn::Join": [
                                    "",
                                    [
                                        "arn:",
                                        {"Ref": "AWS::Partition"},
                                        ":iam::",
                                        {
                                            "Fn::FindInMap": [
                                                "ElbAccountMap",
                                                {"Ref": "AWS::Region"},
                                                "AccountId",
                                            ]
                                        },
                                        ":root",
                                    ],
                                ]
                            }
                        },
                        "Action": "s3:PutObject",
                        "Resource": {"Fn::Sub": "${LogBucket.Arn}/*"},
                    },
                    {
                        "Effect": "Allow",
                        "Principal": {"Service": "delivery.logs.amazonaws.com"},
                        "Action": "s3:PutObject",
                        "Resource": {"Fn::Sub": "${LogBucket.Arn}/*"},
                        "Condition": {
                            "StringEquals": {
                                "s3:x-amz-acl": "bucket-owner-full-control"
                            }
                        },
                    },
                    {
                        "Effect": "Allow",
                        "Principal": {"Service": "delivery.logs.amazonaws.com"},
                        "Action": "s3:GetBucketAcl",
                        "Resource": {"Fn::Sub": "${LogBucket.Arn}"},
                    },
                ],
                "Version": "2012-10-17",
            },
        )
    )


def load_balancer_security_groups(user_data):
    if user_data.elb_type == "network":
        # Network load balancers do not support security groups
        return []

    sg_arns = [*user_data.elb_security_groups]
    allow_cidrs = user_data.allow_cidrs
    if allow_cidrs is None:
        allow_cidrs = [] if len(sg_arns) > 0 else ["0.0.0.0/0"]
    if len(allow_cidrs) > 0:
        sg = add_resource(
            SecurityGroup(
                "DefaultSecurityGroup",
                VpcId=Ref("VpcId"),
                GroupDescription=Sub("Default security group for ${AWS::StackName}"),
                GroupName=Sub("${AWS::StackName}-Default"),
                SecurityGroupEgress=[
                    SecurityGroupRule(
                        CidrIp="0.0.0.0/0",
                        Description="Allow all outbound traffic from ELB",
                        FromPort=0,
                        ToPort=65535,
                        IpProtocol="-1",
                    )
                ],
                SecurityGroupIngress=[
                    SecurityGroupRule(
                        CidrIp=cidr, FromPort=port, ToPort=port, IpProtocol="TCP"
                    )
                    for cidr in allow_cidrs
                    for port in [lsn.port for lsn in user_data.listeners]
                ],
            )
        )

        add_export(
            "ElbSecurityGroup",
            Sub("${AWS::StackName}-sgid"),
            Ref("DefaultSecurityGroup"),
        )

        sg_arns.append(Ref(sg))
    return sg_arns


def load_balancer(user_data):
    attributes = {}
    elb_depends_on = []
    if user_data.access_logs and user_data.access_logs.enabled:
        al = user_data.access_logs
        if al.bucket:
            bucket = al.bucket
        else:
            bucket = Ref(log_bucket(user_data))
            log_bucket_policy()
            elb_depends_on.append("LogBucketPolicy")
        attributes = {
            **attributes,
            "access_logs.s3.enabled": "true",
            "access_logs.s3.prefix": Sub(al.prefix_expr),
            "access_logs.s3.bucket": bucket,
        }

    attributes = {**attributes, **user_data.attributes}

    return add_resource(
        LoadBalancer(
            "LoadBalancer",
            LoadBalancerAttributes=[
                LoadBalancerAttributes(Key=k, Value=v) for k, v in attributes.items()
            ],
            Name=Sub(user_data.name),
            Scheme="internet-facing" if user_data.internet_facing else "internal",
            SecurityGroups=load_balancer_security_groups(user_data),
            Subnets=user_data.subnet_ids,
            Tags=[Tag(k, v) for k, v in user_data.elb_tags],
            Type=user_data.elb_type,
            DependsOn=elb_depends_on,
        )
    )


# We wrap this function in an LRU cache to ensure we only generate one cert per FQDN.
@lru_cache
def certificate_with_fqdn(fqdn, validation_method, hosted_zone_id):
    extra_args = {}
    if validation_method == "DNS" and hosted_zone_id is not None:
        validation_options = [
            DomainValidationOption(DomainName=fqdn, HostedZoneId=hosted_zone_id)
        ]
    else:
        validation_options = []
    return add_resource(
        Certificate(
            clean_title("CertificateFor{}".format(fqdn)),
            DomainName=fqdn,
            ValidationMethod=validation_method,
            DomainValidationOptions=validation_options,
        )
    )


def certificate_arn(user_data, hostname_data):
    if hostname_data.certificate_arn:
        return hostname_data.certificate_arn

    return Ref(
        certificate_with_fqdn(
            hostname_to_fqdn(user_data, hostname_data.hostname),
            user_data.certificate_validation_method,
            user_data.hosted_zone_id,
        )
    )


def health_check_options(hc_data):
    args = {
        "interval_seconds": "HealthCheckIntervalSeconds",
        "timeout_seconds": "HealthCheckTimeoutSeconds",
        "path": "HealthCheckPath",
        "protocol": "HealthCheckProtocol",
        "healthy_threshold_count": "HealthyThresholdCount",
        "unhealth_threshold_count": "UnhealthyThresholdCount",
    }
    hc_data = hc_data.dict()
    return {
        arg: hc_data[key]
        for key, arg in args.items()
        if key in hc_data and hc_data[key] is not None
    }


def target_desc(t):
    return TargetDescription(
        Id=ImportValue(t.import_id) if t.import_id else t.id, **opts_with(Port=t.port)
    )


def target_group_with(user_data, title, default_hc_path, tg_data):
    attrs = tg_data.target_group_attributes

    if user_data.elb_type == "application":
        if "stickiness.enabled" not in attrs:
            attrs["stickiness.enabled"] = "true"
        if "stickiness.type" not in attrs:
            attrs["stickiness.type"] = "lb_cookie"

    if tg_data.target_protocol:
        protocol = tg_data.target_protocol
    elif user_data.elb_type == "network":
        protocol = "TCP"
    else:
        protocol = "HTTP"

    args = {
        "Port": tg_data.target_port,
        "Protocol": protocol,
        "TargetGroupAttributes": [
            TargetGroupAttribute(Key=k, Value=str(v)) for k, v in attrs.items()
        ],
        "Targets": [target_desc(t) for t in tg_data.targets],
        "VpcId": Ref("VpcId"),
    }

    if user_data.elb_type == "application":
        args = {
            **args,
            "HealthCheckPath": default_hc_path,
            "Matcher": Matcher(HttpCode="200-399"),
        }

    if tg_data.health_check:
        args = {**args, **health_check_options(tg_data.health_check)}

    return add_resource(TargetGroup(clean_title(title), **args))


def fixed_response_action(fr_data):
    return Action(
        FixedResponseConfig=FixedResponseConfig(
            ContentType=fr_data.content_type,
            MessageBody=fr_data.message_body,
            StatusCode=str(fr_data.status_code),
        ),
        Type="fixed-response",
    )


def redirect_action(**redirect_data):
    args = ["host", "path", "port", "protocol", "query"]
    return Action(
        RedirectConfig=RedirectConfig(
            **{
                **{"StatusCode": "HTTP_" + str(redirect_data["status_code"])},
                **{
                    camel_case(k): str(redirect_data[k])
                    for k in args
                    if k in redirect_data and redirect_data[k] is not None
                },
            }
        ),
        Type="redirect",
    )


def action_with(user_data, title_context, action_data):
    if action_data.fixed_response:
        return fixed_response_action(action_data.fixed_response)
    if action_data.redirect:
        return redirect_action(**action_data.redirect.dict())

    tg = target_group_with(
        user_data, "{}TargetGroup".format(title_context), "/", action_data
    )
    return Action(TargetGroupArn=Ref(tg), Type="forward")


def paths_with(path_data):
    if isinstance(path_data, str):
        return [path_data]
    for path in path_data:
        yield path
        if "*" not in path and path[-1] != "/":
            yield path + "/*"


def normalize_condition_data(user_data, rule_data):
    hosts = [hostname_to_fqdn(user_data, h) for h in rule_data.hosts]
    paths = rule_data.paths

    if rule_data.priority:
        priority = rule_data.priority
    elif len(hosts) > 0 and len(paths) < 1:
        # Host conditions are provided but no paths. That means this is equivalent to a default action in a
        # single-host ELB. So we put its priority up in a higher range so they'll be evaluated last.
        priority = priority_hash(rule_data.input_values, 48000, 48999)
    else:
        priority = priority_hash(rule_data.input_values, 1000, 47999)

    ret = {"priority": priority}
    if len(hosts) > 0:
        ret["hosts"] = hosts
    if len(paths) > 0:
        ret["paths"] = paths
    if len(rule_data.match_query_string) > 0:
        ret["query_string_matches"] = rule_data.match_query_string
    return ret


def conditions_with(user_data, cond_data):
    conditions = []
    if "hosts" in cond_data:
        conditions.append(
            Condition(
                Field="host-header",
                HostHeaderConfig=HostHeaderConfig(
                    Values=[hostname_to_fqdn(user_data, h) for h in cond_data["hosts"]]
                ),
            )
        )
    if "paths" in cond_data:
        conditions.append(
            Condition(
                Field="path-pattern",
                PathPatternConfig=PathPatternConfig(
                    Values=list(paths_with(cond_data["paths"]))
                ),
            )
        )
    if "query_string_matches" in cond_data:
        conditions.append(
            Condition(
                Field="query-string",
                QueryStringConfig=QueryStringConfig(
                    Values=[
                        QueryStringKeyValue(Key=q.key, Value=q.value)
                        for q in cond_data["query_string_matches"]
                    ]
                ),
            )
        )
    return conditions


def listener_rule(user_data, listener_ref, rule_data):
    rule_title = "Rule{}".format(md5(listener_ref.data, rule_data.input_values)[:7])
    cond_data = normalize_condition_data(user_data, rule_data)
    action = action_with(user_data, rule_title, rule_data)

    return add_resource(
        ListenerRule(
            rule_title,
            Actions=[action],
            ListenerArn=listener_ref,
            Priority=cond_data["priority"],
            Conditions=conditions_with(user_data, cond_data),
        )
    )


def listener(user_data, listener_data):
    port = listener_data.port
    protocol = listener_data.protocol

    if protocol in ["HTTPS", "TLS"]:
        cert_arns = list(
            map(partial(certificate_arn, user_data), listener_data.hostnames)
        )
        primary_certs = [ListenerCertificateEntry(CertificateArn=cert_arns[0])]
    else:
        primary_certs = []
        cert_arns = []

    if listener_data.https_redirect_to:
        default_action = redirect_action(
            protocol="HTTPS",
            port=listener_data.https_redirect_to,
            host="#{host}",
            path="/#{path}",
            query="#{query}",
            status_code=301,
        )
    else:
        default_action = action_with(
            user_data, "DefaultPort{}".format(port), listener_data.default_action
        )

    ret = add_resource(
        Listener(
            "ListenerOnPort{}".format(port),
            Certificates=primary_certs,
            Protocol=protocol,
            LoadBalancerArn=Ref("LoadBalancer"),
            Port=port,
            DefaultActions=[default_action],
        )
    )

    for rule_data in listener_data.rules:
        listener_rule(user_data, Ref(ret), rule_data)

    # For some reason, even though the listener accepts a list of certificate ARNs, you're only allowed to put ONE in
    # that parameter. So we have to associate the others using separate resources.
    for i, cert_arn in enumerate(cert_arns[1:]):
        add_resource(
            ListenerCertificate(
                clean_title("ListenerCert{}OnPort{}".format(i, port)),
                ListenerArn=Ref(ret),
                Certificates=[ListenerCertificateEntry(CertificateArn=cert_arn)],
            )
        )

    return ret


def get_all_fqdns(user_data):
    def it():
        for lsn_data in user_data.listeners:
            for hostname_data in lsn_data.hostnames:
                yield hostname_to_fqdn(user_data, hostname_data.hostname)

    return {n for n in it()}


def ns_entry_route53(zone_id, record_type, name, value, title_suffix=""):
    return add_resource(
        RecordSetType(
            clean_title("RecordSetFor{}{}".format(name, title_suffix)),
            HostedZoneId=zone_id,
            Name=name,
            Type=record_type,
            TTL="300",
            ResourceRecords=[value],
        )
    )


class NsUpdate(AWSCustomObject):
    resource_type = "Custom::NsUpdate"
    props = {
        "ServiceToken": (str, True),
    }


def ns_entry_nsupdate(nsu_model, record_type, name, value):
    lambda_arn = (
        nsu_model.lambda_arn
        if nsu_model.lambda_arn is not None
        else ImportValue(nsu_model.lambda_arn_export_name)
    )

    parts = name.split(".", nsu_model.zone_splits_at)
    zone = parts[-1]
    record = ".".join(parts[:-1])

    args = {
        nsu_model.lambda_record_type_key: record_type,
        nsu_model.lambda_record_key: record,
        nsu_model.lambda_zone_key: zone,
        nsu_model.lambda_value_key: value,
        **nsu_model.lambda_props,
    }

    return add_resource(
        NsUpdate(
            clean_title("NsUpdateFor{}".format(name)),
            validation=False,
            ServiceToken=lambda_arn,
            **args,
        )
    )


def ns_entry_fn(user_data):
    zone_id = user_data.hosted_zone_id
    if zone_id is not None:
        primary = partial(ns_entry_route53, zone_id)
        if len(user_data.alt_hosted_zone_ids) < 1:
            return primary

        def _multizone(record_type, name, value):
            for zone_id in user_data.alt_hosted_zone_ids:
                ns_entry_route53(
                    zone_id, record_type, name, value, title_suffix=f"forZone{zone_id}"
                )
            return primary(record_type, name, value)

        return _multizone

    nsupdate_model = user_data.ns_update
    if nsupdate_model is not None:
        return partial(ns_entry_nsupdate, nsupdate_model)

    # TODO: Instead of doing nothing, add an output to the stack for convenient lookup
    return lambda t, n, v: None


def elb_cnames(user_data):
    efn = ns_entry_fn(user_data)
    for fqdn in get_all_fqdns(user_data):
        efn("CNAME", fqdn, Sub("${LoadBalancer.DNSName}."))


def target_ingress_rules(user_data):
    def _gen():
        for listener in user_data.listeners:
            for action in listener.rules + [listener.default_action]:
                for target in action.targets:
                    if target.sg_id or target.import_sg:
                        yield (
                            target.sg_id,
                            target.import_sg,
                            target.port or action.target_port,
                        )

    for sg_id, import_sg, port in set(_gen()):
        add_resource(
            SecurityGroupIngress(
                clean_title(f"IngressTO{port}FOR{sg_id or import_sg}"),
                Description=Ref("AWS::StackName"),
                FromPort=port,
                ToPort=port,
                IpProtocol="tcp",
                GroupId=sg_id or ImportValue(import_sg),
                SourceSecurityGroupId=Ref("DefaultSecurityGroup"),
            )
        )


def waf_acl_action(constructor, action):
    action = action.capitalize()
    # Some actions have an actual type defined in Troposphere. Others like Count
    # and None in OverrideAction are just dicts.
    fn = globals().get(f"{action}Action")
    return constructor(**{action: fn() if fn else {}})


def waf_visibility_conf(obj):
    return VisibilityConfig(
        CloudWatchMetricsEnabled=obj.metric_name is not None,
        MetricName=obj.metric_name or "Unused",
        SampledRequestsEnabled=obj.sample_requests_enabled,
    )


def waf_ip_set(rule):
    return add_resource(
        IPSet(
            clean_title(f"IPSet{rule.name}"),
            Name=rule.name,
            Addresses=rule.addresses,
            IPAddressVersion=rule.ip_address_version,
            Scope="REGIONAL",
            **opts_with(Description=rule.description),
        )
    )


def waf_rule_ip_set_statement(rule):
    arn = rule if type(rule) is str else GetAtt(waf_ip_set(rule), "Arn")
    return WafStatement(IPSetReferenceStatement=IPSetReferenceStatement(Arn=arn))


def waf_regex_set(rule):
    return add_resource(
        RegexPatternSet(
            clean_title(f"WafRegexSet{rule.name}"),
            Name=rule.name,
            RegularExpressionList=rule.regexes,
            Scope="REGIONAL",
            **opts_with(Description=rule.description),
        )
    )


def waf_rule_regex_set_statement(rule):
    arn = rule.arn if rule.arn else GetAtt(waf_regex_set(rule), "Arn")
    match = (
        {rule.field_to_match: {}}
        if type(rule.field_to_match) is str
        else rule.field_to_match
    )
    transforms = [
        TextTransformation(Priority=t.priority, Type=t.transform_type)
        for t in rule.text_transformations
    ]
    if len(transforms) < 1:
        transforms = [TextTransformation(Priority=0, Type="NONE")]

    return WafStatement(
        RegexPatternSetReferenceStatement=RegexPatternSetReferenceStatement(
            Arn=arn,
            FieldToMatch=FieldToMatch.from_dict(None, match),
            TextTransformations=transforms,
        )
    )


def waf_rule_managed_rule_set_statement(rule):
    return WafStatement(
        ManagedRuleGroupStatement=ManagedRuleGroupStatement(
            Name=rule.name,
            VendorName=rule.vendor_name,
            ExcludedRules=[ExcludedRule(Name=n) for n in rule.excluded_rules],
            **opts_with(Version=rule.version),
        )
    )


def waf_rule_statement(rule):
    rule_dict = rule.__dict__
    for k, v in rule_dict.items():
        if v:
            fn_name = f"waf_rule_{k}_statement"
            fn = globals().get(fn_name)
            if fn:
                return fn(v)


def waf_rule(rule):
    return WebACLRule(
        Name=rule.name,
        Priority=rule.priority,
        VisibilityConfig=waf_visibility_conf(rule),
        Statement=waf_rule_statement(rule),
        **opts_with(
            Action=(rule.action, waf_acl_action, RuleAction),
            OverrideAction=(rule.override_action, waf_acl_action, OverrideAction),
        ),
    )


def waf_acl(acl):
    return add_resource(
        WebACL(
            clean_title(f"Acl{acl.name}"),
            DefaultAction=waf_acl_action(DefaultAction, acl.default_action),
            Scope="REGIONAL",
            Rules=[waf_rule(r) for r in acl.rules],
            VisibilityConfig=waf_visibility_conf(acl),
            **tags_with(acl.acl_tags),
            **opts_with(Description=acl.description, Name=acl.name),
        )
    )


def waf_acl_assoc(acl_model):
    if type(acl_model) is str:
        acl_arn = acl_model
        assoc_title = f"AclAssoc{md5(acl_arn)}"
    else:
        acl_arn = GetAtt(waf_acl(acl_model), "Arn")
        assoc_title = clean_title(f"AclAssocFor{acl_model.name}")

    return add_resource(
        WebACLAssociation(
            assoc_title, ResourceArn=Ref("LoadBalancer"), WebACLArn=acl_arn
        )
    )


def sceptre_handler(user_data):
    add_param(
        "VpcId",
        Type="String",
        Description="The ID of the VPC where the ECS cluster will be created.",
    )

    if user_data is None:
        # We're generating documetation. Return the template with just parameters.
        return TEMPLATE

    data = UserDataModel.parse_obj(user_data)

    load_balancer(data)

    for l in data.listeners:
        listener(data, l)

    elb_cnames(data)
    target_ingress_rules(data)

    for acl in data.waf_acls:
        waf_acl_assoc(acl)

    TEMPLATE.add_mapping(
        "ElbAccountMap",
        {
            "us-east-1": {"AccountId": "127311923021"},
            "us-east-2": {"AccountId": "033677994240"},
            "us-west-1": {"AccountId": "027434742980"},
            "us-west-2": {"AccountId": "797873946194"},
            "af-south-1": {"AccountId": "098369216593"},
            "ca-central-1": {"AccountId": "985666609251"},
            "eu-central-1": {"AccountId": "054676820928"},
            "eu-west-1": {"AccountId": "156460612806"},
            "eu-west-2": {"AccountId": "652711504416"},
            "eu-south-1": {"AccountId": "635631232127"},
            "eu-west-3": {"AccountId": "009996457667"},
            "eu-north-1": {"AccountId": "897822967062"},
            "ap-east-1": {"AccountId": "754344448648"},
            "ap-northeast-1": {"AccountId": "582318560864"},
            "ap-northeast-2": {"AccountId": "600734575887"},
            "ap-northeast-3": {"AccountId": "383597477331"},
            "ap-southeast-1": {"AccountId": "114774131450"},
            "ap-southeast-2": {"AccountId": "783225319266"},
            "ap-south-1": {"AccountId": "718504428378"},
            "me-south-1": {"AccountId": "076674570225"},
            "sa-east-1": {"AccountId": "507241528517"},
            "us-gov-west-1": {"AccountId": "048591011584"},
            "us-gov-east-1": {"AccountId": "190560391635"},
            "cn-north-1": {"AccountId": "638102146993"},
            "cn-northwest-1": {"AccountId": "037604701340"},
        },
    )

    return TEMPLATE.to_json()
