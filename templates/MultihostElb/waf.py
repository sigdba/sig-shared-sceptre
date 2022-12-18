import troposphere.wafv2
from troposphere import GetAtt, Ref, Sub
from troposphere.firehose import BufferingHints as FirehoseBufferingHints
from troposphere.firehose import (
    CloudWatchLoggingOptions as FirehoseCloudWatchLoggingOptions,
)
from troposphere.firehose import DeliveryStream as FirehoseDeliveryStream
from troposphere.firehose import S3DestinationConfiguration as FirehoseS3DestinationConf
from troposphere.iam import Policy as IamPolicy
from troposphere.iam import Role as IamRole
from troposphere.logs import LogGroup, LogStream
from troposphere.wafv2 import (
    DefaultAction,
    ExcludedRule,
    FieldToMatch,
    IPSet,
    IPSetReferenceStatement,
)
from troposphere.wafv2 import LoggingConfiguration as WafLoggingConf
from troposphere.wafv2 import (
    ManagedRuleGroupStatement,
    OverrideAction,
    RegexPatternSet,
    RegexPatternSetReferenceStatement,
    RuleAction,
)

if int(troposphere.__version__.split(".")[0]) > 3:
    from troposphere.wafv2 import Statement as WafStatement
else:
    from troposphere.wafv2 import StatementOne as WafStatement

from troposphere.wafv2 import (
    TextTransformation,
    VisibilityConfig,
    WebACL,
    WebACLAssociation,
    WebACLRule,
)

from util import add_resource, add_resource_once, clean_title, md5, opts_with, tags_with


def waf_acl_action(constructor, action):
    action = action.capitalize()
    # Some actions have an actual type defined in Troposphere. Others like Count
    # and None in OverrideAction are just dicts.
    fn = getattr(troposphere.wafv2, f"{action}Action", None)
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


def waf_log_firehose_s3_dest_conf(s3_model, title_prefix):
    role = add_resource(
        IamRole(
            f"{title_prefix}Role",
            AssumeRolePolicyDocument={
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"Service": "firehose.amazonaws.com"},
                        "Action": "sts:AssumeRole",
                    }
                ],
            },
            Policies=[
                IamPolicy(
                    PolicyName="AllowToBucket",
                    PolicyDocument={
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Effect": "Allow",
                                "Action": [
                                    "s3:AbortMultipartUpload",
                                    "s3:GetBucketLocation",
                                    "s3:GetObject",
                                    "s3:ListBucket",
                                    "s3:ListBucketMultipartUploads",
                                    "s3:PutObject",
                                ],
                                "Resource": [s3_model.bucket_arn],
                            }
                        ],
                    },
                )
            ],
        )
    )

    log_group_name = Sub("/aws/kinesisfirehose/${AWS::StackName}")
    log_stream_name = title_prefix
    if s3_model.cloudwatch_enabled:
        add_resource_once(
            f"{title_prefix}LogGroup",
            lambda n: LogGroup(n, LogGroupName=log_group_name, RetentionInDays=30),
        )
        add_resource(
            LogStream(
                f"{title_prefix}LogStream",
                LogGroupName=log_group_name,
                LogStreamName=log_stream_name,
            ),
        )

    return FirehoseS3DestinationConf(
        BucketARN=s3_model.bucket_arn,
        CompressionFormat=s3_model.compression_format,
        Prefix=Sub(s3_model.prefix_expr),
        ErrorOutputPrefix=Sub(s3_model.error_prefix_expr),
        RoleARN=GetAtt(role, "Arn"),
        BufferingHints=FirehoseBufferingHints(
            **opts_with(
                IntervalInSeconds=s3_model.buffer_seconds, SizeInMBs=s3_model.buffer_mb
            )
        ),
        CloudWatchLoggingOptions=FirehoseCloudWatchLoggingOptions(
            Enabled=s3_model.cloudwatch_enabled,
            LogGroupName=log_group_name,
            LogStreamName=log_stream_name,
        ),
    )


def waf_log_firehose_dest_arn(firehose_model, title_prefix):
    title = f"{title_prefix}FirehoseDeliveryStream"
    return GetAtt(
        add_resource(
            FirehoseDeliveryStream(
                title,
                # For some dratted reason, WAF log streams must be prefixed with
                # 'aws-waf-logs-' so we have to give a static name here.
                DeliveryStreamName=Sub(
                    "aws-waf-logs-${AWS::StackName}-" + title_prefix
                ),
                DeliveryStreamType="DirectPut",
                S3DestinationConfiguration=waf_log_firehose_s3_dest_conf(
                    firehose_model.s3, title
                ),
            )
        ),
        "Arn",
    )


def waf_log_dest_arn(log_model, title_prefix):
    if log_model.firehose:
        return waf_log_firehose_dest_arn(log_model.firehose, title_prefix)
    raise ValueError("No WAF logging destinations defined")


def waf_logging_conf(log_model, title_prefix, acl_resource):
    title = f"{title_prefix}Logging"
    return add_resource(
        WafLoggingConf(
            title,
            ResourceArn=GetAtt(acl_resource, "Arn"),
            LogDestinationConfigs=[waf_log_dest_arn(log_model, title)],
        )
    )


def waf_acl(acl):
    title = clean_title(f"Acl{acl.name}")
    ret = add_resource(
        WebACL(
            title,
            DefaultAction=waf_acl_action(DefaultAction, acl.default_action),
            Scope="REGIONAL",
            Rules=[waf_rule(r) for r in acl.rules],
            VisibilityConfig=waf_visibility_conf(acl),
            **tags_with(acl.acl_tags),
            **opts_with(Description=acl.description, Name=acl.name),
        )
    )

    if acl.logging:
        waf_logging_conf(acl.logging, title, ret)

    return ret


def acl_assoc(acl_model):
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
