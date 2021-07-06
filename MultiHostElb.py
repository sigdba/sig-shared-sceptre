import hashlib
from functools import lru_cache, partial
from troposphere import Template, Ref, Sub, Parameter, GetAtt, Tag
from troposphere.elasticloadbalancingv2 import LoadBalancer, LoadBalancerAttributes, Listener, ListenerRule, \
    ListenerCertificate, Certificate as ListenerCertificateEntry, FixedResponseConfig, ForwardConfig, TargetGroup, \
    Matcher, TargetGroupAttribute, TargetDescription, Action, RedirectConfig, Condition, HostHeaderConfig, \
    PathPatternConfig
from troposphere.s3 import Bucket, BucketPolicy, LifecycleConfiguration, LifecycleRule, LifecycleRuleTransition, \
    PublicAccessBlockConfiguration
from troposphere.certificatemanager import Certificate, DomainValidationOption
from troposphere.route53 import RecordSet, RecordSetType
from troposphere.ec2 import SecurityGroup, SecurityGroupRule

TEMPLATE = Template()
PRIORITY_CACHE = []


# TODO: Replace all uses of isinstance(_, str) with this.
def as_list(s):
    """If s is a string it returns [s]. Otherwise it returns list(s)."""
    if isinstance(s, str):
        return [s]
    return list(s)


def md5(*s):
    return hashlib.md5(''.join(map(str, s)).encode('utf-8')).hexdigest()


def priority_hash(s, range_start=1000, range_end=47999):
    ret = int(md5(s), 16) % (range_end - range_start) + range_start
    while ret in PRIORITY_CACHE:
        ret += 1
    PRIORITY_CACHE.append(ret)
    return ret


def hostname_to_fqdn(user_data, hostname):
    return hostname if '.' in hostname else '{}.{}'.format(hostname, user_data['domain'])


def add_resource(r):
    TEMPLATE.add_resource(r)
    return r


def add_params(t):
    t.add_parameter(Parameter("VpcId", Type="String"))


def clean_title(s):
    return s.replace('-', 'DASH') \
        .replace('.', 'DOT') \
        .replace('_', 'US') \
        .replace('*', 'STAR') \
        .replace('?', 'QM') \
        .replace('/', 'SLASH') \
        .replace(' ', 'SP')


def camel_case(s):
    return ''.join(map(str.title, s.split('_')))


def log_bucket(user_data):
    return add_resource(Bucket(
        'LogBucket',
        LifecycleConfiguration=LifecycleConfiguration(Rules=[LifecycleRule(
            ExpirationInDays=user_data.get('access_log_retain_days', 90),
            Status='Enabled'
        )]),
        PublicAccessBlockConfiguration=PublicAccessBlockConfiguration(
            BlockPublicAcls=True,
            BlockPublicPolicy=True,
            IgnorePublicAcls=True,
            RestrictPublicBuckets=True
        )
    ))


def log_bucket_policy():
    return add_resource(BucketPolicy(
        'LogBucketPolicy',
        Bucket=Ref('LogBucket'),
        PolicyDocument={
            "Statement": [{
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
                                        "AccountId"
                                    ]
                                },
                                ":root"
                            ]
                        ]
                    }
                },
                "Action": "s3:PutObject",
                "Resource": {"Fn::Sub": "${LogBucket.Arn}/*"}
            }, {
                "Effect": "Allow",
                "Principal": {"Service": "delivery.logs.amazonaws.com"},
                "Action": "s3:PutObject",
                "Resource": {"Fn::Sub": "${LogBucket.Arn}/*"},
                "Condition": {"StringEquals": {"s3:x-amz-acl": "bucket-owner-full-control"}}
            }, {
                "Effect": "Allow",
                "Principal": {"Service": "delivery.logs.amazonaws.com"},
                "Action": "s3:GetBucketAcl",
                "Resource": {"Fn::Sub": "${LogBucket.Arn}"}
            }],
            "Version": "2012-10-17"
        }
    ))


def load_balancer_security_groups(user_data):
    sg_arns = user_data.get('elb_security_groups', [])
    allow_cidrs = user_data.get('allow_cidrs', [] if len(sg_arns) > 0 else ['0.0.0.0/0'])
    if len(allow_cidrs) > 0:
        sg = add_resource(SecurityGroup(
            "DefaultSecurityGroup",
            VpcId=Ref('VpcId'),
            GroupDescription=Sub('Default security group for ${AWS::StackName}'),
            GroupName=Sub('${AWS::StackName}-Default'),
            SecurityGroupEgress=[SecurityGroupRule(
                CidrIp='0.0.0.0/0',
                Description='Allow all outbound traffic from ELB',
                FromPort=0,
                ToPort=65535,
                IpProtocol='-1'
            )],
            SecurityGroupIngress=[SecurityGroupRule(
                CidrIp=cidr,
                FromPort=port,
                ToPort=port,
                IpProtocol='TCP'
            ) for cidr in allow_cidrs for port in [lsn['port'] for lsn in user_data['listeners']]]
        ))
        sg_arns.append(Ref(sg))
    return sg_arns


def load_balancer(user_data):
    attributes = {**{
        'access_logs.s3.enabled': 'true',
        'access_logs.s3.prefix': Sub('${AWS::StackName}-access.')
    }, **user_data.get('elb_attributes', {})}

    if attributes['access_logs.s3.enabled'] == 'true' and 'access_logs.s3.bucket' not in attributes:
        attributes['access_logs.s3.bucket'] = Ref(log_bucket(user_data))
        log_bucket_policy()
        elb_depends_on = 'LogBucketPolicy'
    else:
        elb_depends_on = []

    return add_resource(LoadBalancer(
        'LoadBalancer',
        LoadBalancerAttributes=[LoadBalancerAttributes(Key=k, Value=v) for k, v in attributes.items()],
        Name=user_data.get('name', Ref('AWS::StackName')),
        Scheme='internet-facing' if user_data.get('internet_facing', False) else 'internal',
        SecurityGroups=load_balancer_security_groups(user_data),
        Subnets=user_data['subnet_ids'],
        Tags=[Tag(k, v) for k, v in user_data.get('elb_tags', {})],
        Type='application',
        DependsOn=elb_depends_on
    ))


# We wrap this function in an LRU cache to ensure we only generate one cert per FQDN.
@lru_cache
def certificate_with_fqdn(fqdn, validation_method, hosted_zone_id):
    extra_args = {}
    if validation_method == 'DNS' and hosted_zone_id is not None:
        validation_options = [DomainValidationOption(DomainName=fqdn, HostedZoneId=hosted_zone_id)]
    else:
        validation_options = []
    return add_resource(Certificate(
        clean_title('CertificateFor{}'.format(fqdn)),
        DomainName=fqdn,
        ValidationMethod=validation_method,
        DomainValidationOptions=validation_options
    ))


def normalize_hostname_data(user_data, hostname_data):
    if isinstance(hostname_data, str):
        return normalize_hostname_data(user_data, {'hostname': hostname_data})

    hostname = hostname_data['hostname']
    return {**hostname_data,
            'fqdn': hostname_to_fqdn(user_data, hostname)}


def certificate_arn(user_data, hostname_data):
    hostname_data = normalize_hostname_data(user_data, hostname_data)
    if 'certificate_arn' in hostname_data:
        return hostname_data['certificate_arn']

    return Ref(certificate_with_fqdn(hostname_data['fqdn'],
                                     user_data.get('certificate_validation_method', 'DNS'),
                                     user_data.get('hosted_zone_id', None)))


def health_check_options(hc_data):
    args = {'interval_seconds': 'HealthCheckIntervalSeconds',
            'timeout_seconds': 'HealthCheckTimeoutSeconds',
            'path': 'HealthCheckPath'}
    return {arg: hc_data[key] for key, arg in args.items() if key in hc_data}


def target_desc(t_data):
    if isinstance(t_data, str):
        return TargetDescription(Id=t_data)

    args = {'id': 'Id', 'port': 'Port'}
    return TargetDescription(**{arg: t_data[key] for key, arg in args.items()})


def target_group_with(title, default_hc_path, tg_data):
    attrs = tg_data.get('target_group_attributes', {})

    if 'stickiness.enabled' not in attrs:
        attrs['stickiness.enabled'] = 'true'
    if 'stickiness.type' not in attrs:
        attrs['stickiness.type'] = 'lb_cookie'

    args = {'HealthCheckPath': default_hc_path,
            'Matcher': Matcher(HttpCode='200-399'),
            'Port': tg_data.get('target_port', 8080),
            'Protocol': tg_data.get('target_protocol', 'HTTP'),
            'TargetGroupAttributes': [TargetGroupAttribute(Key=k, Value=str(v)) for k, v in attrs.items()],
            'Targets': [target_desc(t) for t in tg_data.get('targets', [])],
            'VpcId': Ref('VpcId')}

    if 'health_check' in tg_data:
        args = {**args, **health_check_options(tg_data['health_check'])}

    return add_resource(TargetGroup(clean_title(title), **args))


def fixed_response_action(fr_data):
    return Action(FixedResponseConfig=FixedResponseConfig(
        ContentType=fr_data.get('content_type', 'text/plain'),
        MessageBody=fr_data['message_body'],
        StatusCode=str(fr_data.get('status_code', 200))
    ), Type='fixed-response')


def redirect_action(**redirect_data):
    args = ['host', 'path', 'port', 'protocol', 'query']
    return Action(RedirectConfig=RedirectConfig(
        **{**{'StatusCode': 'HTTP_' + str(redirect_data.get('status_code', 302))},
           **{camel_case(k): str(redirect_data[k]) for k in args if k in redirect_data}}
    ), Type='redirect')


def action_with(title_context, action_data):
    if 'fixed_response' in action_data:
        return fixed_response_action(action_data['fixed_response'])
    if 'redirect' in action_data:
        return redirect_action(**action_data['redirect'])

    tg = target_group_with('{}TargetGroup'.format(title_context), '/', action_data)
    return Action(TargetGroupArn=Ref(tg), Type='forward')


def paths_with(path_data):
    if isinstance(path_data, str):
        return [path_data]
    for path in path_data:
        yield path
        if '*' not in path and path[-1] != '/':
            yield path + '/*'


def normalize_condition_data(user_data, rule_data):
    hosts = [hostname_to_fqdn(user_data, h) for h in as_list(rule_data.get('hosts', rule_data.get('host', [])))]
    paths = rule_data.get('paths', as_list(rule_data.get('path', [])))

    if 'priority' in rule_data:
        priority = rule_data['priority']
    elif len(hosts) > 0 and len(paths) < 1:
        # Host conditions are provided but no paths. That means this is equivalent to a default action in a
        # single-host ELB. So we put its priority up in a higher range so they'll be evaluated last.
        priority = priority_hash(rule_data, 48000, 48999)
    else:
        priority = priority_hash(rule_data, 1000, 47999)

    ret = {'priority': priority}
    if len(hosts) > 0:
        ret['hosts'] = hosts
    if len(paths) > 0:
        ret['paths'] = paths
    return ret


def conditions_with(user_data, cond_data):
    conditions = []
    if 'hosts' in cond_data:
        conditions.append(Condition(
            Field='host-header',
            HostHeaderConfig=HostHeaderConfig(Values=[hostname_to_fqdn(user_data, h) for h in cond_data['hosts']])
        ))
    if 'paths' in cond_data:
        conditions.append(Condition(
            Field='path-pattern',
            PathPatternConfig=PathPatternConfig(Values=list(paths_with(cond_data['paths'])))
        ))
    return conditions


def listener_rule(user_data, listener_ref, rule_data):
    rule_title = 'Rule{}'.format(md5(listener_ref, rule_data)[:7])
    cond_data = normalize_condition_data(user_data, rule_data)
    action = action_with(rule_title, rule_data)

    return add_resource(ListenerRule(
        rule_title,
        Actions=[action],
        ListenerArn=listener_ref,
        Priority=cond_data['priority'],
        Conditions=conditions_with(user_data, cond_data)
    ))


def listener(user_data, listener_data):
    port = int(listener_data['port'])

    if 'protocol' in listener_data:
        protocol = listener_data['protocol']
    elif port == 80:
        protocol = 'HTTP'
    elif port == 443:
        protocol = 'HTTPS'
    else:
        raise ValueError('You must specify a protocol for listener on non-standard port: {}'.format(port))

    if protocol == 'HTTPS':
        cert_arns = list(map(partial(certificate_arn, user_data), listener_data['hostnames']))
        primary_certs = [ListenerCertificateEntry(CertificateArn=cert_arns[0])]
    else:
        primary_certs = []
        cert_arns = []

    if 'https_redirect_to' in listener_data:
        default_action = redirect_action(protocol='HTTPS',
                                         port=listener_data['https_redirect_to'],
                                         host='#{host}',
                                         path='/#{path}',
                                         query='#{query}',
                                         status_code=301)
    else:
        default_action = action_with('DefaultPort{}'.format(port), listener_data.get('default_action', {}))

    ret = add_resource(Listener(
        "ListenerOnPort{}".format(port),
        Certificates=primary_certs,
        Protocol=protocol,
        LoadBalancerArn=Ref('LoadBalancer'),
        Port=port,
        DefaultActions=[default_action]
    ))

    for rule_data in listener_data.get('rules', []):
        listener_rule(user_data, Ref(ret), rule_data)

    # For some reason, even though the listener accepts a list of certificate ARNs, you're only allowed to put ONE in
    # that parameter. So we have to associate the others using separate resources.
    for i, cert_arn in enumerate(cert_arns[1:]):
        add_resource(ListenerCertificate(
            clean_title('ListenerCert{}OnPort{}'.format(i, port)),
            ListenerArn=Ref(ret),
            Certificates=[ListenerCertificateEntry(CertificateArn=cert_arn)]
        ))

    return ret


def get_all_fqdns(user_data):
    def it():
        for lsn_data in user_data['listeners']:
            for hostname_data in lsn_data.get('hostnames', []):
                yield normalize_hostname_data(user_data, hostname_data)['fqdn']

    return {n for n in it()}


def route53_records(user_data):
    zone_id = user_data.get('hosted_zone_id', None)
    if zone_id is None:
        return

    for fqdn in get_all_fqdns(user_data):
        add_resource(RecordSetType(
            clean_title('RecordSetFor{}'.format(fqdn)),
            HostedZoneId=zone_id,
            Name=fqdn,
            Type='CNAME',
            TTL='300',
            ResourceRecords=[GetAtt('LoadBalancer', 'DNSName')]
        ))


def sceptre_handler(user_data):
    add_params(TEMPLATE)
    load_balancer(user_data)

    for l_data in user_data['listeners']:
        listener(user_data, l_data)

    route53_records(user_data)

    TEMPLATE.add_mapping('ElbAccountMap', {
        'us-east-1': {'AccountId': '127311923021'},
        'us-east-2': {'AccountId': '033677994240'},
        'us-west-1': {'AccountId': '027434742980'},
        'us-west-2': {'AccountId': '797873946194'},
        'af-south-1': {'AccountId': '098369216593'},
        'ca-central-1': {'AccountId': '985666609251'},
        'eu-central-1': {'AccountId': '054676820928'},
        'eu-west-1': {'AccountId': '156460612806'},
        'eu-west-2': {'AccountId': '652711504416'},
        'eu-south-1': {'AccountId': '635631232127'},
        'eu-west-3': {'AccountId': '009996457667'},
        'eu-north-1': {'AccountId': '897822967062'},
        'ap-east-1': {'AccountId': '754344448648'},
        'ap-northeast-1': {'AccountId': '582318560864'},
        'ap-northeast-2': {'AccountId': '600734575887'},
        'ap-northeast-3': {'AccountId': '383597477331'},
        'ap-southeast-1': {'AccountId': '114774131450'},
        'ap-southeast-2': {'AccountId': '783225319266'},
        'ap-south-1': {'AccountId': '718504428378'},
        'me-south-1': {'AccountId': '076674570225'},
        'sa-east-1': {'AccountId': '507241528517'},
        'us-gov-west-1': {'AccountId': '048591011584'},
        'us-gov-east-1': {'AccountId': '190560391635'},
        'cn-north-1': {'AccountId': '638102146993'},
        'cn-northwest-1': {'AccountId': '037604701340'},
    })

    return TEMPLATE.to_json()
