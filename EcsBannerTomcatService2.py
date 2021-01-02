from troposphere import Template, Ref, Sub, Parameter, ImportValue
from troposphere.ecs import TaskDefinition, Service, ContainerDefinition, PortMapping, LogConfiguration, Environment, \
    LoadBalancer, DeploymentConfiguration, Volume, EFSVolumeConfiguration, MountPoint
from troposphere.elasticloadbalancingv2 import ListenerRule, TargetGroup, Action, Condition, Matcher, \
    TargetGroupAttribute

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


def container_mount_point(data):
    return MountPoint(ContainerPath=data['container_path'],
                      SourceVolume=data['source_volume'],
                      ReadOnly=data.get('read_only', False))


def container_def(data):
    # NB: container_memory is the hard limit on RAM presented to the container. It will be killed if it tries to
    #     allocate more. container_memory_reservation is the soft limit and docker will try to keep the container to
    #     this value.
    #
    # TODO: container_memory_reservation is not mandatory. Maybe it should default to undefined?
    container_memory = data.get("container_memory", 512)
    container_memory_reservation = data.get("container_memory_reservation", container_memory)

    # TODO: Gather data about non-heap overhead so that we can make sensible defaults for tomcat_memory_args based
    #       on container_memory and container_memory_reservation.
    tomcat_memory_args = data.get("tomcat_memory_args", "-Xms%sM -Xmx%sM" % (container_memory_reservation,
                                                                             container_memory))

    # Base environment variables from the stack
    env_map = {
        "AWS_DEFAULT_REGION": Ref("AWS::Region"),
        "TOMCAT_MEMORY_ARGS": tomcat_memory_args
    }

    # Add stack-specific vars
    env_map.update(data.get("env_vars", {}))

    # Convert the environment map to a list of Environment objects
    environment = [Environment(Name=k, Value=v) for (k, v) in env_map.items()]

    # Configure mount points
    mount_points = [container_mount_point(p) for p in data.get('mount_points', [])]

    return ContainerDefinition(
        Name=data.get("name", "tomcat"),
        Environment=environment,
        Essential=True,
        Hostname=Ref("AWS::StackName"),
        Image=data["image"],
        Memory=container_memory,
        MemoryReservation=container_memory_reservation,
        MountPoints=mount_points,
        PortMappings=[PortMapping(ContainerPort=data.get("tomcat_port", 8080))],

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


def task_def(container_defs, efs_volumes):
    volumes = [Volume(Name=v['name'],
                      EFSVolumeConfiguration=EFSVolumeConfiguration(FilesystemId=v["fs_id"])) for v in efs_volumes]

    return add_resource(TaskDefinition("TaskDef",
                                       Volumes=volumes,
                                       Family=Ref("AWS::StackName"),
                                       ContainerDefinitions=container_defs))


def target_group(health_check_path):
    return add_resource(TargetGroup(clean_title("TargetGroupFOR%s" % health_check_path),
                                    HealthCheckProtocol="HTTP",
                                    HealthCheckPath=health_check_path,

                                    HealthCheckIntervalSeconds=60,
                                    HealthCheckTimeoutSeconds=30,
                                    UnhealthyThresholdCount=5,

                                    Matcher=Matcher(HttpCode="200-399"),
                                    Port=8080,  # TODO: Remove this?
                                    Protocol="HTTP",
                                    TargetGroupAttributes=[
                                        TargetGroupAttribute(Key="stickiness.enabled", Value="true"),
                                        TargetGroupAttribute(Key="stickiness.type", Value="lb_cookie")],
                                    TargetType="instance",
                                    VpcId=Ref("VpcId")))


def listener_rule(tg, rule):
    path = rule["path"]
    priority = rule["priority"]

    values = [path, "%s/*" % path]
    return add_resource(ListenerRule("ListenerRule%s" % priority,
                                     Actions=[Action(
                                         Type="forward",
                                         TargetGroupArn=Ref(tg))],
                                     Conditions=[Condition(Field="path-pattern", Values=values)],
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

    tomcat_containers = []
    listener_rules = []
    lb_mappings = []
    for c in sceptre_user_data["tomcat_containers"]:
        container = container_def(c)
        tomcat_containers.append(container)

        if "target_group_arn" in c:
            # We're injecting into an existing target. Don't set up listener rules.
            target_group_arn = c["target_group_arn"]
        else:
            # Create target group and associated listener rules
            rules = c["rules"]
            health_check_path = c.get("health_check_path", "%s/" % rules[0]["path"])
            tg = target_group(health_check_path)

            for rule in rules:
                listener_rules.append(listener_rule(tg, rule))

            target_group_arn = Ref(tg)

        lb_mappings.append(LoadBalancer(ContainerName=container.Name,
                                        # TODO: Ugly hack, do better.
                                        ContainerPort=container.PortMappings[0].ContainerPort,
                                        TargetGroupArn=target_group_arn))

    task_def(tomcat_containers, efs_volumes)
    service(listener_rules, lb_mappings)

    return TEMPLATE.to_json()
