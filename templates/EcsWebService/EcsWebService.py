import json

import troposphere
from troposphere import GetAtt, Parameter, Ref, Sub, Tags
from troposphere.awslambda import Code, Function, Permission
from troposphere.cloudformation import AWSCustomObject
from troposphere.ecs import (
    ContainerDefinition,
    ContainerDependency,
    DeploymentConfiguration,
    EFSVolumeConfiguration,
    Environment,
)
from troposphere.ecs import HealthCheck as ContainerHealthCheck
from troposphere.ecs import Host as HostVolumeConfiguration
from troposphere.ecs import (
    AwsvpcConfiguration,
    LinuxParameters,
    LoadBalancer,
    LogConfiguration,
    MountPoint,
    NetworkConfiguration,
    PlacementStrategy,
    PortMapping,
    Secret,
    Service,
    TaskDefinition,
    Volume,
)
from troposphere.elasticloadbalancingv2 import (
    Condition,
    HostHeaderConfig,
    ListenerRule,
    Matcher,
    PathPatternConfig,
    TargetGroup,
    TargetGroupAttribute,
)
from troposphere.events import Rule as EventRule
from troposphere.events import Target as EventTarget
from troposphere.iam import Policy, Role


if int(troposphere.__version__.split(".")[0]) > 3:
    from troposphere.elasticloadbalancingv2 import ListenerRuleAction
else:
    from troposphere.elasticloadbalancingv2 import Action as ListenerRuleAction

import model
from util import (
    TEMPLATE,
    add_resource,
    add_resource_once,
    clean_title,
    md5,
    opts_with,
    read_resource,
)
from security_group import security_group

PRIORITY_CACHE = []


def priority_hash(rule):
    ret = (
        int(md5(str(rule.dict(exclude_defaults=True, exclude_unset=True))), 16) % 48000
        + 1000
    )
    while ret in PRIORITY_CACHE:
        ret += 1
    PRIORITY_CACHE.append(ret)
    return ret


def add_params(t):
    t.add_parameter(
        Parameter(
            "VpcId", Type="String", Description="The ID of the VPC of the ECS cluster"
        )
    )
    t.add_parameter(
        Parameter(
            "ListenerArn",
            Type="String",
            Description="The ARN of the ELB listener which will be used by this service",
        )
    )
    t.add_parameter(
        Parameter(
            "ClusterArn",
            Type="String",
            Description="The ARN or name of the ECS cluster",
        )
    )
    t.add_parameter(
        Parameter(
            "DesiredCount",
            Type="Number",
            Default="1",
            Description="The desired number of instances of this service",
        )
    )
    t.add_parameter(
        Parameter(
            "MaximumPercent",
            Type="Number",
            Default="200",
            Description="The maximum percent of `DesiredCount` allowed to be running during updates.",
        )
    )
    t.add_parameter(
        Parameter(
            "MinimumHealthyPercent",
            Type="Number",
            Default="100",
            Description="The minimum number of running instances of this service to keep running during an update.",
        )
    )


def execution_role_secret_statement(secret_arn):
    if ":secretsmanager:" in secret_arn:
        return {
            "Action": "secretsmanager:GetSecretValue",
            "Resource": secret_arn,
            "Effect": "Allow",
        }
    elif ":ssm:" in secret_arn:
        return {
            "Action": "ssm:GetParameters",
            "Resource": secret_arn,
            "Effect": "Allow",
        }
    else:
        return {
            "Action": "ssm:GetParameters",
            "Resource": Sub(
                "arn:aws:ssm:${AWS::Region}:${AWS::AccountId}:parameter/%s" % secret_arn
            ),
            "Effect": "Allow",
        }


def execution_role(secret_arns):
    policies = [
        Policy(
            PolicyName="root",
            PolicyDocument={
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "logs:CreateLogGroup",
                            "logs:CreateLogStream",
                            "logs:PutLogEvents",
                            "logs:DescribeLogStreams",
                        ],
                        "Resource": ["arn:aws:logs:*:*:*"],
                    }
                ],
            },
        )
    ]
    if secret_arns:
        policies.append(
            Policy(
                PolicyName="secrets",
                PolicyDocument={
                    "Version": "2012-10-17",
                    "Statement": [
                        execution_role_secret_statement(s) for s in secret_arns
                    ],
                },
            )
        )
    return add_resource(
        Role(
            "TaskExecutionRole",
            AssumeRolePolicyDocument={
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"Service": ["ecs-tasks.amazonaws.com"]},
                        "Action": ["sts:AssumeRole"],
                    }
                ],
            },
            ManagedPolicyArns=[
                "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
            ],
            Policies=policies,
        )
    )


def container_mount_point(data):
    return MountPoint(
        ContainerPath=data.container_path,
        SourceVolume=data.source_volume,
        ReadOnly=data.read_only,
    )


def port_mappings(container_data):
    if len(container_data.port_mappings) > 0:
        return [
            PortMapping(ContainerPort=m.container_port)
            for m in container_data.port_mappings
        ]
    elif container_data.container_port:
        return [PortMapping(ContainerPort=container_data.container_port)]
    else:
        return []


def lambda_fn_for_codebuild():
    lambda_execution_role()
    return add_resource_once(
        "LambdaFunctionForCodeBuild",
        lambda name: Function(
            name,
            Description="Builds a container image",
            Handler="index.lambda_handler",
            Role=GetAtt("LambdaExecutionRole", "Arn"),
            Runtime="python3.9",
            MemorySize=128,
            Timeout=900,
            Code=Code(ZipFile=Sub(read_resource("CodeBuildResourceLambda.py"))),
        ),
    )


class ImageBuild(AWSCustomObject):
    resource_type = "Custom::ImageBuild"
    props = {
        "ServiceToken": (str, True),
        "ProjectName": (str, True),
        "EnvironmentVariablesOverride": (list, False),
        "RepositoryName": (str, False),
    }


def image_build(container_name, build):
    lambda_fn_for_codebuild()
    return add_resource(
        ImageBuild(
            "ImageBuildFor{}".format(container_name),
            ServiceToken=GetAtt("LambdaFunctionForCodeBuild", "Arn"),
            ProjectName=build.codebuild_project_name,
            EnvironmentVariablesOverride=[v.dict() for v in build.env_vars],
            RepositoryName=build.ecr_repo_name,
        )
    )


def container_def(hostname, container):
    # NB: container_memory is the hard limit on RAM presented to the container. It will be killed if it tries to
    #     allocate more. container_memory_reservation is the soft limit and docker will try to keep the container to
    #     this value.
    #
    # TODO: container_memory_reservation is not mandatory. Maybe it should default to undefined?
    container_memory = container.container_memory
    container_memory_reservation = (
        container.container_memory_reservation
        if container.container_memory_reservation
        else container.container_memory
    )

    # Base environment variables from the stack
    env_map = {"AWS_DEFAULT_REGION": Ref("AWS::Region")}

    # Add stack-specific vars
    env_map.update(container.env_vars)

    # Convert the environment map to a list of Environment objects
    environment = [Environment(Name=k, Value=v) for (k, v) in env_map.items()]

    # Convert the secrets map into a list of Secret objects
    secrets = [Secret(Name=k, ValueFrom=v) for (k, v) in container.secrets.items()]

    # Configure mount points
    mount_points = [container_mount_point(p) for p in container.mount_points]

    if container.image_build is not None:
        image = GetAtt(image_build(container.name, container.image_build), "ImageURI")
    else:
        image = container.image

    extra_args = {}
    if len(container.linux_parameters) > 0:
        extra_args["LinuxParameters"] = LinuxParameters(**container.linux_parameters)
    if len(container.command) > 0:
        extra_args["Command"] = container.command
    if container.depends_on:
        extra_args["DependsOn"] = [
            ContainerDependency(**d) for d in container.depends_on
        ]
    if container.container_health_check:
        extra_args["HealthCheck"] = ContainerHealthCheck(
            **container.container_health_check
        )

    return ContainerDefinition(
        Name=container.name,
        Environment=environment,
        Secrets=secrets,
        Essential=True,
        Image=image,
        Memory=container_memory,
        MemoryReservation=container_memory_reservation,
        MountPoints=mount_points,
        PortMappings=port_mappings(container),
        Links=container.links,
        # TODO: We might want to check for failed connection pools and this can probably be done
        #       using HealthCheck here which runs a command inside the container.
        LogConfiguration=LogConfiguration(
            LogDriver="awslogs",
            Options={
                "awslogs-group": Sub("/ecs/${AWS::StackName}"),
                "awslogs-region": Ref("AWS::Region"),
                "awslogs-stream-prefix": "ecs",
                "awslogs-create-group": True,
            },
        ),
        **opts_with(Hostname=hostname),
        **extra_args,
        **container.container_extra_props,
    )


def efs_volume(v):
    return Volume(
        Name=v.name,
        EFSVolumeConfiguration=EFSVolumeConfiguration(
            FilesystemId=v.fs_id, **opts_with(RootDirectory=v.root_directory)
        ),
    )


def host_volume(v):
    return Volume(Name=v.name, Host=HostVolumeConfiguration(SourcePath=v.source_path))


def task_def(user_data, container_defs, exec_role):
    volumes = [efs_volume(v) for v in user_data.efs_volumes] + [
        host_volume(v) for v in user_data.host_volumes
    ]

    return add_resource(
        TaskDefinition(
            "TaskDef",
            Volumes=volumes,
            Family=Ref("AWS::StackName"),
            ContainerDefinitions=container_defs,
            **opts_with(
                ExecutionRoleArn=(exec_role, Ref),
                Cpu=user_data.cpu,
                Memory=user_data.memory,
                RequiresCompatibilities=user_data.requires_compatibilities,
                NetworkMode=user_data.network_mode,
            ),
        )
    )


def target_group(
    target_type,
    protocol,
    health_check,
    target_group_props,
    default_health_check_path,
    port=None,
):
    if not health_check:
        health_check = model.HealthCheckModel()
    if not health_check.path:
        health_check.path = default_health_check_path
    attrs = target_group_props.attributes

    if "stickiness.enabled" not in attrs:
        attrs["stickiness.enabled"] = "true"
    if "stickiness.type" not in attrs:
        attrs["stickiness.type"] = "lb_cookie"

    title = clean_title(
        f"TargetGroupPORT{port}HC{health_check.path}"
        if port
        else f"TargetGroupFOR{health_check.path}"
    )

    return add_resource(
        TargetGroup(
            title,
            HealthCheckProtocol=protocol,
            HealthCheckPath=health_check.path,
            HealthCheckIntervalSeconds=health_check.interval_seconds,
            HealthCheckTimeoutSeconds=health_check.timeout_seconds,
            UnhealthyThresholdCount=health_check.unhealthy_threshold_count,
            Matcher=Matcher(HttpCode=health_check.http_code),
            Port=port or 8080,  # This is overridden by the targets themselves.
            Protocol=protocol,
            TargetGroupAttributes=[
                TargetGroupAttribute(Key=k, Value=str(v)) for k, v in attrs.items()
            ],
            TargetType=target_type,
            VpcId=Ref("VpcId"),
            Tags=Tags(Name=Sub("${AWS::StackName}: %s" % health_check.path)),
            **opts_with(HealthyThresholdCount=health_check.healthy_threshold_count),
        )
    )


def listener_rule(tg_arn, rule, listener_arn):
    path = rule.path
    priority = rule.priority if rule.priority else priority_hash(rule)

    # TODO: We may want to support more flexible rules in the way
    #       MultiHostElb.py does. But one thing to note if we do that, rules
    #       having a single path and no host would need to have their priority
    #       hash generated as above (priority_hash(path)). Otherwise it'll cause
    #       issues when updating older stacks.
    if path == "/":
        conditions = []
    else:
        path_patterns = [path, "%s/*" % path]
        conditions = [
            Condition(
                Field="path-pattern",
                PathPatternConfig=PathPatternConfig(Values=path_patterns),
            )
        ]

    if rule.host:
        conditions.append(
            Condition(
                Field="host-header",
                HostHeaderConfig=HostHeaderConfig(Values=[rule.host]),
            )
        )

    return add_resource(
        ListenerRule(
            "ListenerRule%s" % priority,
            Actions=[ListenerRuleAction(Type="forward", TargetGroupArn=tg_arn)],
            Conditions=conditions,
            ListenerArn=listener_arn,
            Priority=priority,
        )
    )


def service_network_configuration(user_data):
    if user_data.network_mode != "awsvpc":
        return None

    security_groups = []
    if user_data.security_group:
        security_groups.append(
            Ref(security_group("ServiceSecurityGroup", user_data.security_group))
        )
    if user_data.security_group_ids:
        security_groups += user_data.security_group_ids

    return NetworkConfiguration(
        AwsvpcConfiguration=AwsvpcConfiguration(
            SecurityGroups=security_groups,
            **opts_with(Subnets=user_data.subnet_ids),
        )
    )


def service(user_data, listener_rules, lb_mappings):
    return add_resource(
        Service(
            "Service",
            DependsOn=[r.title for r in listener_rules],
            TaskDefinition=Ref("TaskDef"),
            Cluster=Ref("ClusterArn"),
            DesiredCount=Ref("DesiredCount"),
            DeploymentConfiguration=DeploymentConfiguration(
                MaximumPercent=Ref("MaximumPercent"),
                MinimumHealthyPercent=Ref("MinimumHealthyPercent"),
            ),
            LoadBalancers=lb_mappings,
            **opts_with(
                LaunchType=user_data.launch_type,
                Tags=(user_data.service_tags, Tags),
                NetworkConfiguration=service_network_configuration(user_data),
                PlacementStrategies=(
                    user_data.placement_strategies,
                    lambda ps: [
                        PlacementStrategy(Field=s.field, Type=s.type) for s in ps
                    ],
                ),
            ),
        )
    )


def lambda_execution_role():
    # TODO: See if we can tighten this a bit.
    return add_resource_once(
        "LambdaExecutionRole",
        lambda name: Role(
            name,
            Policies=[
                Policy(
                    PolicyName="lambda-inline",
                    PolicyDocument={
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Effect": "Allow",
                                "Action": [
                                    "autoscaling:CompleteLifecycleAction",
                                    "logs:CreateLogGroup",
                                    "logs:CreateLogStream",
                                    "logs:PutLogEvents",
                                    "ecr:DescribeImages",
                                    "ecr:DescribeRepositories",
                                    "ecr:ListImages",
                                    "codebuild:StartBuild",
                                    "codebuild:BatchGetBuilds",
                                    "ecs:UpdateService",
                                ],
                                "Resource": "*",
                            }
                        ],
                    },
                )
            ],
            AssumeRolePolicyDocument={
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"Service": ["lambda.amazonaws.com"]},
                        "Action": ["sts:AssumeRole"],
                    }
                ],
            },
            ManagedPolicyArns=[],
            Path="/",
        ),
    )


def scheduling_lambda():
    return add_resource(
        Function(
            "SchedulingLambda",
            Description="Updates service properties on a schedule",
            Handler="index.lambda_handler",
            Role=GetAtt("LambdaExecutionRole", "Arn"),
            Runtime="python3.9",
            MemorySize=128,
            Timeout=60,
            Code=Code(ZipFile=Sub(read_resource("ScheduleLambda.py"))),
        )
    )


def lambda_invoke_permission(rule):
    return add_resource(
        Permission(
            "LambdaInvokePermission" + rule.title,
            FunctionName=Ref("SchedulingLambda"),
            Action="lambda:InvokeFunction",
            Principal="events.amazonaws.com",
            SourceArn=GetAtt(rule, "Arn"),
        )
    )


def scheduling_rule(rule_props):
    cron_expr = rule_props.cron
    rule_hash = md5(cron_expr)[:7]
    desired_count = rule_props.desired_count

    return add_resource(
        EventRule(
            "ScheduleRule" + rule_hash,
            ScheduleExpression="cron(%s)" % cron_expr,
            Description=rule_props.description,
            Targets=[
                EventTarget(
                    Id="ScheduleRule" + rule_hash,
                    Arn=GetAtt("SchedulingLambda", "Arn"),
                    Input=json.dumps({"desired_count": desired_count}),
                )
            ],
        )
    )


def sceptre_handler(sceptre_user_data):
    add_params(TEMPLATE)

    if sceptre_user_data is None:
        # We're generating documetation. Return the template with just parameters.
        return TEMPLATE

    user_data = model.UserDataModel(**sceptre_user_data)

    # If we're using secrets, we need to define an execution role
    secret_arns = [v for c in user_data.containers for k, v in c.secrets.items()]
    if len(secret_arns) > 0 or user_data.launch_type == "FARGATE":
        exec_role = execution_role(secret_arns)
    else:
        exec_role = None

    hostname = None if user_data.network_mode == "awsvpc" else Ref("AWS::StackName")
    target_group_type = "ip" if user_data.network_mode == "awsvpc" else "instance"

    containers = []
    listener_rules = []
    lb_mappings = []
    for c in user_data.containers:
        container = container_def(hostname, c)
        containers.append(container)

        target_group_arn = None
        if c.target_group_arn:
            # We're injecting into an existing target. Don't set up listener rules.
            target_group_arn = c.target_group_arn

        if c.rules:
            default_port = container.PortMappings[0].ContainerPort
            default_tg = None
            for rule in c.rules:
                if rule.container_port or rule.target_group_arn:
                    if rule.target_group_arn:
                        tg_arn = rule.target_group_arn
                    else:
                        tg_arn = Ref(
                            target_group(
                                target_group_type,
                                rule.protocol or c.protocol,
                                rule.health_check or c.health_check,
                                rule.target_group or c.target_group,
                                f"{rule.path}/",
                                port=rule.container_port or default_port,
                            )
                        )
                    lb_mappings.append(
                        LoadBalancer(
                            ContainerName=container.Name,
                            ContainerPort=rule.container_port or default_port,
                            TargetGroupArn=tg_arn,
                        )
                    )
                else:
                    if not default_tg:
                        if target_group_arn:
                            # TODO: Add validation to the model to prevent this.
                            # TODO: Should port_mappings let you put a container_port on a TG?
                            raise ValueError("The default TG has already been created.")
                        default_tg = target_group(
                            target_group_type,
                            c.protocol,
                            c.health_check,
                            c.target_group,
                            "%s/" % c.rules[0].path,
                        )
                        target_group_arn = Ref(default_tg)
                    tg_arn = Ref(default_tg)
                listener_rules.append(
                    listener_rule(tg_arn, rule, rule.listener_arn or Ref("ListenerArn"))
                )

        if target_group_arn is not None:
            if len(container.PortMappings) < 1:
                raise ValueError(
                    "Container '%s' connects to an ELB but does not specify port_mappings or container_port"
                    % c["name"]
                )
            lb_mappings.append(
                LoadBalancer(
                    ContainerName=container.Name,
                    ContainerPort=container.PortMappings[0].ContainerPort,
                    TargetGroupArn=target_group_arn,
                )
            )

    task_def(user_data, containers, exec_role)
    service(
        user_data,
        listener_rules,
        lb_mappings,
    )

    schedule = user_data.schedule
    if len(schedule) > 0:
        lambda_execution_role()
        scheduling_lambda()
        for p in schedule:
            rule = scheduling_rule(p)
            lambda_invoke_permission(rule)

    for r in TEMPLATE.resources.items():
        print(type(r.value))

    return TEMPLATE.to_json()
