from troposphere import Template, Ref, Sub, Parameter, ImportValue
from troposphere.ecs import TaskDefinition, Service, ContainerDefinition, PortMapping, LogConfiguration, Environment, \
    LoadBalancer, DeploymentConfiguration, Volume, EFSVolumeConfiguration, MountPoint, Secret
from troposphere.elasticloadbalancingv2 import ListenerRule, TargetGroup, Action, Condition, Matcher, \
    TargetGroupAttribute, PathPatternConfig
from troposphere.iam import Role, Policy

TEMPLATE = Template()


def add_resource(r):
    TEMPLATE.add_resource(r)
    return r


def clean_title(s):
    return s.replace('-', 'DASH').replace('.', 'DOT').replace('_', 'US').replace('*', 'STAR').replace('?',
                                                                                                      'QM').replace('/',
                                                                                                                    'SLASH')


def add_params(t):
    t.add_parameter(Parameter("VpcId", Type="String"))
    t.add_parameter(Parameter("ListenerArn", Type="String"))
    t.add_parameter(Parameter("EcsEnv", Type="String"))
    t.add_parameter(Parameter("DesiredCount", Type="Number", Default="1"))
    t.add_parameter(Parameter("MaximumPercent", Type="Number", Default="200"))
    t.add_parameter(Parameter("MinimumHealthyPercent", Type="Number", Default="100"))


def execution_role():
    return add_resource(Role('TaskExecutionRole',
                             AssumeRolePolicyDocument={
                                 "Version": "2012-10-17",
                                 "Statement": [{
                                     "Effect": "Allow",
                                     "Principal": {"Service": ["ecs-tasks.amazonaws.com"]},
                                     "Action": ['sts:AssumeRole']
                                 }]
                             },
                             ManagedPolicyArns=[
                                 'arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy'],
                             Policies=[
                                 Policy(
                                     PolicyName="root",
                                     PolicyDocument={
                                         "Version": '2012-10-17',
                                         "Statement": [
                                             {"Effect": "Allow",
                                              "Action": ['kms:Decrypt'],
                                              # TODO: Tighten this based on inputs
                                              "Resource": ['*']},
                                             {"Effect": "Allow",
                                              "Action": ['ssm:GetParameters'],
                                              # TODO: Tighten this based on inputs
                                              "Resource": ['*']},
                                             {"Effect": "Allow",
                                              "Action": ["logs:CreateLogGroup",
                                                         "logs:CreateLogStream",
                                                         "logs:PutLogEvents",
                                                         "logs:DescribeLogStreams"],
                                              "Resource": ['arn:aws:logs:*:*:*']}]
                                     }
                                 )
                             ]))


def container_mount_point(data):
    return MountPoint(ContainerPath=data['container_path'],
                      SourceVolume=data['source_volume'],
                      ReadOnly=data.get('read_only', False))


def port_mappings(container_data):
    if 'port_mappings' in container_data:
        return [PortMapping(ContainerPort=m['container_port']) for m in container_data['port_mappings']]
    elif 'container_port' in container_data:
        return [PortMapping(ContainerPort=container_data['container_port'])]
    else:
        return []


def container_def(data):
    # NB: container_memory is the hard limit on RAM presented to the container. It will be killed if it tries to
    #     allocate more. container_memory_reservation is the soft limit and docker will try to keep the container to
    #     this value.
    #
    # TODO: container_memory_reservation is not mandatory. Maybe it should default to undefined?
    container_memory = data.get("container_memory", 512)
    container_memory_reservation = data.get("container_memory_reservation", container_memory)

    # Base environment variables from the stack
    env_map = {
        "AWS_DEFAULT_REGION": Ref("AWS::Region")
    }

    # Add stack-specific vars
    env_map.update(data.get("env_vars", {}))

    # Convert the environment map to a list of Environment objects
    environment = [Environment(Name=k, Value=v) for (k, v) in env_map.items()]

    # Convert the secrets map into a list of Secret objects
    secrets = [Secret(Name=k, ValueFrom=v) for (k, v) in data.get('secrets', {}).items()]

    # Configure mount points
    mount_points = [container_mount_point(p) for p in data.get('mount_points', [])]

    return ContainerDefinition(
        Name=data.get("name", "main"),
        Environment=environment,
        Secrets=secrets,
        Essential=True,
        Hostname=Ref("AWS::StackName"),
        Image=data["image"],
        Memory=container_memory,
        MemoryReservation=container_memory_reservation,
        MountPoints=mount_points,
        PortMappings=port_mappings(data),
        Links=data.get('links', []),

        # TODO: We might want to check for failed connection pools and this can probably be done
        #       using HealthCheck here which runs a command inside the container.

        LogConfiguration=LogConfiguration(
            LogDriver="awslogs",
            Options={
                "awslogs-group": Sub("/ecs/${AWS::StackName}"),
                "awslogs-region": Ref("AWS::Region"),
                "awslogs-stream-prefix": "ecs",
                "awslogs-create-group": True
            }
        ))


def task_def(container_defs, efs_volumes, exec_role):
    volumes = [Volume(Name=v['name'],
                      EFSVolumeConfiguration=EFSVolumeConfiguration(FilesystemId=v["fs_id"])) for v in efs_volumes]

    exec_role_arn = Ref(exec_role) if exec_role is not None else None

    return add_resource(TaskDefinition("TaskDef",
                                       Volumes=volumes,
                                       Family=Ref("AWS::StackName"),
                                       ContainerDefinitions=container_defs,
                                       ExecutionRoleArn=exec_role_arn))


def target_group(protocol, health_check, default_health_check_path):
    health_check_path = health_check.get('path', default_health_check_path)

    return add_resource(TargetGroup(clean_title("TargetGroupFOR%s" % health_check_path),
                                    HealthCheckProtocol=protocol,
                                    HealthCheckPath=health_check_path,

                                    HealthCheckIntervalSeconds=60,
                                    HealthCheckTimeoutSeconds=30,
                                    UnhealthyThresholdCount=5,

                                    Matcher=Matcher(HttpCode="200-399"),
                                    Port=8080,  # This is overridden by the targets themselves.
                                    Protocol=protocol,
                                    TargetGroupAttributes=[
                                        TargetGroupAttribute(Key="stickiness.enabled", Value="true"),
                                        TargetGroupAttribute(Key="stickiness.type", Value="lb_cookie")],
                                    TargetType="instance",
                                    VpcId=Ref("VpcId")))


def listener_rule(tg, rule):
    path = rule["path"]
    priority = rule["priority"]

    path_patterns = [path, "%s/*" % path]
    return add_resource(ListenerRule("ListenerRule%s" % priority,
                                     Actions=[Action(
                                         Type="forward",
                                         TargetGroupArn=Ref(tg))],
                                     Conditions=[Condition(Field="path-pattern",
                                                           PathPatternConfig=PathPatternConfig(Values=path_patterns))],
                                     ListenerArn=Ref("ListenerArn"),
                                     Priority=priority))


def service(listener_rules, lb_mappings):
    return add_resource(Service("Service",
                                DependsOn=[r.title for r in listener_rules],
                                TaskDefinition=Ref("TaskDef"),
                                Cluster=ImportValue(Sub("${EcsEnv}-EcsEnv-EcsCluster")),
                                DesiredCount=Ref("DesiredCount"),
                                DeploymentConfiguration=DeploymentConfiguration(
                                    MaximumPercent=Ref("MaximumPercent"),
                                    MinimumHealthyPercent=Ref("MinimumHealthyPercent")),
                                LoadBalancers=lb_mappings))


def sceptre_handler(sceptre_user_data):
    add_params(TEMPLATE)

    efs_volumes = sceptre_user_data.get("efs_volumes", [])

    # If we're using secrets, we need to define an execution role
    exec_role = execution_role() if len(list(filter(lambda x: 'secrets' in x, sceptre_user_data['containers']))) > 0 \
        else None

    containers = []
    listener_rules = []
    lb_mappings = []
    for c in sceptre_user_data["containers"]:
        container = container_def(c)
        containers.append(container)

        if "target_group_arn" in c:
            # We're injecting into an existing target. Don't set up listener rules.
            target_group_arn = c["target_group_arn"]
        elif 'rules' in c:
            # Create target group and associated listener rules
            rules = c["rules"]
            health_check = c.get('health_check', {})
            protocol = c.get('protocol', 'HTTP')
            tg = target_group(protocol, health_check, "%s/" % rules[0]["path"])

            for rule in rules:
                listener_rules.append(listener_rule(tg, rule))

            target_group_arn = Ref(tg)
        else:
            target_group_arn = None

        if target_group_arn is not None:
            lb_mappings.append(LoadBalancer(ContainerName=container.Name,
                                            # TODO: Ugly hack, do better.
                                            ContainerPort=container.PortMappings[0].ContainerPort,
                                            TargetGroupArn=target_group_arn))

    task_def(containers, efs_volumes, exec_role)
    service(listener_rules, lb_mappings)

    return TEMPLATE.to_json()
