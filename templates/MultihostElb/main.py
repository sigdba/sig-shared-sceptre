from functools import lru_cache, partial

import troposphere
from troposphere import GetAtt, ImportValue, Ref, Sub, Tag
from troposphere.certificatemanager import Certificate, DomainValidationOption
from troposphere.cloudformation import AWSCustomObject
from troposphere.ec2 import SecurityGroup, SecurityGroupIngress, SecurityGroupRule
from troposphere.elasticloadbalancingv2 import Certificate as ListenerCertificateEntry
from troposphere.elasticloadbalancingv2 import (
    Condition,
    FixedResponseConfig,
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
    SourceIpConfig,
    RedirectConfig,
    SubnetMapping,
    TargetDescription,
    TargetGroup,
    TargetGroupAttribute,
)

import waf

if int(troposphere.__version__.split(".")[0]) > 3:
    from troposphere.elasticloadbalancingv2 import Action as ListenerDefaultAction
    from troposphere.elasticloadbalancingv2 import (
        ListenerRuleAction as ListenerRuleAction,
    )
else:
    from troposphere.elasticloadbalancingv2 import (
        Action as ListenerRuleAction,
        Action as ListenerDefaultAction,
    )

from troposphere.route53 import AliasTarget, RecordSetType
from troposphere.s3 import (
    Bucket,
    BucketPolicy,
    LifecycleConfiguration,
    LifecycleRule,
    PublicAccessBlockConfiguration,
)

from model import AllowCidrModel, UserDataModel
from util import (
    TEMPLATE,
    add_export,
    add_param,
    add_resource,
    clean_title,
    md5,
    opts_with,
    sceptre_handle,
)
import elb


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
        allow_cidrs = [] if len(sg_arns) > 0 else [AllowCidrModel(cidr="0.0.0.0/0")]
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
                        CidrIp=cidr.cidr,
                        FromPort=port,
                        ToPort=port,
                        IpProtocol="TCP",
                        **opts_with(Description=cidr.description),
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
            Tags=[Tag(k, v) for k, v in user_data.elb_tags.items()],
            Type=user_data.elb_type,
            DependsOn=elb_depends_on,
            **opts_with(
                Subnets=user_data.subnet_ids,
                SubnetMappings=(
                    user_data.subnet_mappings,
                    lambda ms: [SubnetMapping(**m) for m in ms],
                ),
            ),
        )
    )


# We wrap this function in an LRU cache to ensure we only generate one cert per FQDN.
@lru_cache
def certificate_with_fqdn(fqdn, validation_method, hosted_zone_id):
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
    hosted_zone_id = (
        hostname_data.hosted_zone_id[0]
        if hostname_data.hosted_zone_id
        else user_data.hosted_zone_id
    )

    return Ref(
        certificate_with_fqdn(
            hostname_to_fqdn(user_data, hostname_data.hostname),
            hostname_data.certificate_validation_method
            or user_data.certificate_validation_method,
            hosted_zone_id,
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

    http_codes = tg_data.health_check.http_codes if tg_data.health_check else "200-399"

    if user_data.elb_type == "application":
        args = {
            **args,
            "HealthCheckPath": default_hc_path,
            "Matcher": Matcher(HttpCode=http_codes),
        }

    if tg_data.target_type:
        args = {**args, "TargetType": tg_data.target_type}

    if tg_data.health_check:
        args = {**args, **health_check_options(tg_data.health_check)}

    return add_resource(TargetGroup(clean_title(title), **args))


def fixed_response_action(fr_data, action_type=ListenerRuleAction):
    return action_type(
        FixedResponseConfig=FixedResponseConfig(
            ContentType=fr_data.content_type,
            MessageBody=fr_data.message_body,
            StatusCode=str(fr_data.status_code),
        ),
        Type="fixed-response",
    )


def redirect_action(action_type=ListenerRuleAction, **redirect_data):
    args = ["host", "path", "port", "protocol", "query"]
    return action_type(
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


def action_with(user_data, title_context, action_data, action_type=ListenerRuleAction):
    if action_data.fixed_response:
        return fixed_response_action(
            action_data.fixed_response, action_type=action_type
        )
    if action_data.redirect:
        return redirect_action(**action_data.redirect.dict(), action_type=action_type)

    tg = target_group_with(
        user_data, "{}TargetGroup".format(title_context), "/", action_data
    )
    return action_type(TargetGroupArn=Ref(tg), Type="forward")


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
        priority = elb.host_only_priority_hash(rule_data.input_values)
    else:
        priority = elb.host_path_priority_hash(rule_data.input_values)

    ret = {"priority": priority}
    if len(hosts) > 0:
        ret["hosts"] = hosts
    if len(paths) > 0:
        ret["paths"] = paths
    if len(rule_data.match_query_string) > 0:
        ret["query_string_matches"] = rule_data.match_query_string
    if len(rule_data.source_ips) > 0:
        ret["source_ips"] = rule_data.source_ips
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
    if "source_ips" in cond_data:
        conditions.append(
            Condition(
                Field="source-ip",
                SourceIpConfig=SourceIpConfig(Values=cond_data["source_ips"]),
            )
        )
    return conditions


def listener_rule(user_data, listener_ref, rule_data):
    rule_title = rule_data.rule_title or "Rule{}".format(
        md5(
            listener_ref.data,
            rule_data.paths,
            rule_data.hosts,
            rule_data.match_query_string,
            rule_data.priority,
        )[:7]
    )
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
            action_type=ListenerDefaultAction,
            protocol="HTTPS",
            port=listener_data.https_redirect_to,
            host="#{host}",
            path="/#{path}",
            query="#{query}",
            status_code=301,
        )
    else:
        default_action = action_with(
            user_data,
            "DefaultPort{}".format(port),
            listener_data.default_action,
            action_type=ListenerDefaultAction,
        )

    ret = add_resource(
        Listener(
            "ListenerOnPort{}".format(port),
            Certificates=primary_certs,
            Protocol=protocol,
            LoadBalancerArn=Ref("LoadBalancer"),
            Port=port,
            DefaultActions=[default_action],
            **opts_with(SslPolicy=listener_data.ssl_policy),
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


def get_all_hostnames(user_data):
    for lsn_data in user_data.listeners:
        for hostname_data in lsn_data.hostnames:
            yield hostname_data


def ns_entry_route53(route53_opts, zone_id, record_type, name, value, title_suffix=""):
    if route53_opts.record_type == "alias":
        opts = {
            "Type": "A",
            "AliasTarget": AliasTarget(
                DNSName=value,
                HostedZoneId=GetAtt("LoadBalancer", "CanonicalHostedZoneID"),
            ),
        }
    else:
        opts = {
            "Type": record_type,
            "ResourceRecords": [value],
            "TTL": "300",
        }
    return add_resource(
        RecordSetType(
            clean_title("RecordSetFor{}{}".format(name, title_suffix)),
            HostedZoneId=zone_id,
            Name=name,
            **opts,
        )
    )


class NsUpdate(AWSCustomObject):
    resource_type = "Custom::NsUpdate"
    props = {"ServiceToken": (str, True)}


def ns_entry_nsupdate(nsu_model, record_type, name, value, _title_suffix=""):
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
            clean_title("NsUpdateFor{}{}".format(name, _title_suffix)),
            validation=False,
            ServiceToken=lambda_arn,
            **args,
        )
    )


def ns_entry_fn_global(user_data):
    """Returns a function which creates DNS resources based on the configuration
    in user_data."""
    zone_id = user_data.hosted_zone_id
    if zone_id is not None:
        primary = partial(ns_entry_route53, user_data.route53, zone_id)
        if len(user_data.alt_hosted_zone_ids) < 1:
            return primary

        def _multizone(record_type, name, value):
            for zone_id in user_data.alt_hosted_zone_ids:
                ns_entry_route53(
                    user_data.route53,
                    zone_id,
                    record_type,
                    name,
                    value,
                    title_suffix=f"forZone{zone_id}",
                )
            return primary(record_type, name, value)

        return _multizone

    nsupdate_models = user_data.ns_update
    if nsupdate_models is not None and len(nsupdate_models) > 0:
        if len(nsupdate_models) < 2:
            return partial(ns_entry_nsupdate, nsupdate_models[0])

        def _multiserver(*args):
            return [
                ns_entry_nsupdate(m, _title_suffix=md5(m), *args)
                for m in nsupdate_models
            ][0]

        return _multiserver

    # TODO: Instead of doing nothing, add an output to the stack for convenient lookup
    return lambda t, n, v: None


def ns_entry_fn(user_data):
    """Returns a function which creates DNS resources based on the configuration
    in user_data. This function wraps ns_entry_fn_global and adds a keyword
    argument which can be used to override the default behavior."""

    default_fn = ns_entry_fn_global(user_data)

    def ret(record_type, name, value, hosted_zone_id=None):
        if hosted_zone_id:
            return ns_entry_route53(
                user_data.route53,
                hosted_zone_id,
                record_type,
                name,
                value,
                title_suffix=f"ovrZone{hosted_zone_id}",
            )

        return default_fn(record_type, name, value)

    return ret


def get_all_fqdns(user_data):
    return {
        hostname_to_fqdn(user_data, n.hostname) for n in get_all_hostnames(user_data)
    }


def elb_cnames(user_data):
    # We need a de-duplicated list of hostnames along with their overriding
    # hosted_zone_id (if any). To do this we create a generator which yields
    # tuples then push them into a set to remove duplicates.
    def it():
        for h in get_all_hostnames(user_data):
            if h.hosted_zone_id or h.hosted_zone_id == []:
                for z in h.hosted_zone_id:
                    yield (h.hostname, z)
            else:
                yield (h.hostname, None)

    efn = ns_entry_fn(user_data)
    for fqdn, zone_id in {p for p in it()}:
        efn("CNAME", fqdn, Sub("${LoadBalancer.DNSName}."), hosted_zone_id=zone_id)


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


def instance_sg():
    return add_resource(
        SecurityGroup(
            "InstanceSecurityGroup",
            VpcId=Ref("VpcId"),
            GroupDescription=Sub("Instance security group for ${AWS::StackName}"),
            GroupName=Sub("${AWS::StackName}-InstanceSg"),
            SecurityGroupIngress=[
                SecurityGroupRule(
                    FromPort=-1,
                    ToPort=-1,
                    IpProtocol="-1",
                    Description=Sub("Allow all from ${AWS::StackName}"),
                    SourceSecurityGroupId=Ref("DefaultSecurityGroup"),
                )
            ],
        )
    )


def add_params():
    add_param(
        "VpcId",
        Type="String",
        Description="The ID of the VPC where the ECS cluster will be created.",
    )


def main(data):
    load_balancer(data)

    for lsn in data.listeners:
        listener(data, lsn)

    elb_cnames(data)
    target_ingress_rules(data)

    for acl in data.waf_acls:
        waf.acl_assoc(acl)

    if data.create_instance_sg:
        inst_sg = instance_sg()
        add_export(
            "InstanceSg",
            Sub("${AWS::StackName}-instance-sg-id"),
            Ref(inst_sg),
        )

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


def sceptre_handler(user_data):
    return sceptre_handle(add_params, main, UserDataModel, user_data)
