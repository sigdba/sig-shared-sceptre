import operator
import os
from datetime import datetime, timedelta

import boto3

REGION = "${AWS::Region}"

# Check if we're in a test environment, and if so set the region from the
# environment or use a default.
if "AWS::Region" in REGION:
    REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
print("REGION:", REGION)


ECS = boto3.client("ecs", region_name=REGION)
CW = boto3.client("cloudwatch", region_name=REGION)


def env(k, default=None):
    if k in os.environ:
        ret = os.environ[k]
        if len(ret) > 0:
            return ret
    if default:
        return default
    raise ValueError(f"Required environment variable {k} not set")


def chunks(it, chunk_size):
    lst = list(it)
    return [lst[i : i + chunk_size] for i in range(0, len(lst), chunk_size)]


def get_cluster_arns():
    def _gen():
        for page in ECS.get_paginator("list_clusters").paginate():
            for arn in page["clusterArns"]:
                yield arn

    lst = os.environ.get("ECS_CLUSTERS", "").strip()
    if len(lst) < 1:
        raise ValueError("ECS_CLUSTERS environment variable is required")
    if lst == "ALL":
        return list(_gen())
    names = set(filter(lambda s: len(s) > 0, map(str.strip, lst.split(","))))
    return list(filter(lambda a: a in names or a.split("/")[-1] in names, _gen()))


def get_service_arns(cluster):
    paginator = ECS.get_paginator("list_services")
    for page in paginator.paginate(cluster=cluster, launchType="EC2"):
        for arn in page["serviceArns"]:
            yield arn


def get_services(cluster):
    for chunk in chunks(get_service_arns(cluster), 10):
        res = ECS.describe_services(cluster=cluster, services=chunk, include=["TAGS"])
        for svc in res["services"]:
            yield svc


def get_task_def(arn):
    return ECS.describe_task_definition(taskDefinition=arn)["taskDefinition"]


def require_active(svc):
    if os.environ.get("REQUIRE_ACTIVE", "true") != "true":
        return None
    if svc["status"] == "ACTIVE" and svc["runningCount"] > 0:
        return None
    return "not active"


def require_stable(svc):
    return (
        None
        if svc["pendingCount"] == 0 and svc["desiredCount"] == svc["runningCount"]
        else "not stable"
    )


def require_tag(key, val, svc, fn=operator.eq, default=None):
    tags = {t["key"]: t["value"] for t in svc.get("tags", [])}
    cur_val = tags.get(key, default)
    return (
        None
        if fn(cur_val, val)
        else f"tag '{key}': '{cur_val}' not {fn.__name__} '{val}'"
    )


def require_opt_in(svc):
    return require_tag(
        os.environ.get("ENABLING_TAG", "AutoAdjustMemoryReservation"),
        "true",
        svc,
        default="unset"
        if os.environ.get("REQUIRE_OPT_IN", "true") == "true"
        else "true",
    )


def is_candidate_svc(svc):
    reqs = [require_active, require_stable, require_opt_in]
    for r in reqs:
        msg = r(svc)
        if msg:
            print(f"SKIPPING service '{svc['serviceName']}': {msg}")
            return False
    return True


def metric_spec(cluster_name, service_name, container_name):
    return {
        "Namespace": "ECS/Monitor",
        "MetricName": "MemoryUsage",
        "Dimensions": [
            {"Name": "ClusterName", "Value": cluster_name},
            {"Name": "ContainerName", "Value": container_name},
            {"Name": "Group", "Value": f"service:{service_name}"},
        ],
    }


def datapoint_to_mb(dp):
    unit = dp["Unit"]
    if unit == "Bytes":
        return int(dp["Maximum"] / 1024 / 1024)
    raise ValueError(f"Unknown unit: {unit}")


def get_max_mem_by_day(
    start_time, end_time, cluster_name, service_name, container_name
):
    dps = CW.get_metric_statistics(
        StartTime=start_time,
        EndTime=end_time,
        Period=24 * 60 * 60,
        Statistics=["Maximum"],
        **metric_spec(cluster_name, service_name, container_name),
    )["Datapoints"]
    dps.sort(key=lambda p: p["Timestamp"])
    return [datapoint_to_mb(p) for p in dps]


def dead_zone_mb():
    return int(os.environ.get("MIN_CHANGE_MB", 64))


def recommend_res(cur_max, cur_res, peak_mem):
    min_over = int(os.environ.get("MIN_OVERHEAD_MB", 1))
    max_over = float(env("MAX_OVERHEAD_MB", "inf"))
    over_pct = float(os.environ.get("OVERHEAD_PCT", 0))
    ret = int(
        min(
            cur_max,
            peak_mem + max_over,
            max(over_pct / 100.0 * peak_mem + peak_mem, peak_mem + min_over, 6),
        )
    )
    # Always adjust upward if the observed peak is greater than the current
    # reservation. We never want to be UNDER provisioned so we ignore the dead
    # zone in this case.
    if peak_mem > cur_res:
        return ret
    # To avoid constant, unencessary tweaking, ignore changes smaller than a
    # certain amount.
    if abs(cur_res - ret) < dead_zone_mb():
        return cur_res
    return ret


def update_task_def(old_task_def):
    omit = [
        "compatibilities",
        "memory",
        "taskDefinitionArn",
        "revision",
        "status",
        "requiresAttributes",
        "registeredAt",
        "registeredBy",
    ]
    new_task_def = {k: v for k, v in old_task_def.items() if k not in omit}
    return ECS.register_task_definition(**new_task_def)["taskDefinition"][
        "taskDefinitionArn"
    ]


def update_service(cluster, service, task_def):
    if os.environ.get("DRY_RUN", "unset") == "true":
        print("DRY_RUN is true. Will not update service.")
        return
    task_def_arn = update_task_def(task_def)
    ECS.update_service(cluster=cluster, service=service, taskDefinition=task_def_arn)


def candidate_services():
    for cluster_arn in get_cluster_arns():
        cluster_name = cluster_arn.split("/")[-1]
        for svc in get_services(cluster_arn):
            if is_candidate_svc(svc):
                yield {**svc, "clusterName": cluster_name}


def adjusted_task_def(svc):
    req_days = int(os.environ.get("REQUIRE_STAT_DAYS", 7))
    consider_days = int(os.environ.get("CONSIDER_STAT_DAYS", 14))
    now = datetime.utcnow()
    start_time = now - timedelta(days=consider_days)
    cluster_name = svc["clusterName"]
    svc_name = svc["serviceName"]
    task_def = get_task_def(svc["taskDefinition"])
    task_mem_limit = int(task_def.get("memory", -1))
    changed = False
    for cdef in task_def["containerDefinitions"]:
        cname = cdef["name"]
        mem_limit = cdef.get("memory", task_mem_limit)
        if mem_limit < 1:
            print(
                f"WARNING: Unable to compute memory limit for {cluster_name}/{svc['serviceName']}/{cname}. SKIPPING."
            )
            continue
        mem_res = cdef.get("memoryReservation", mem_limit)
        max_mem_days = get_max_mem_by_day(
            start_time, now, cluster_name, svc_name, cname
        )
        # Don't adjust if we don't have enough stat data
        if len(max_mem_days) < req_days:
            print(
                f"SKIPPING service '{svc_name}': less than {req_days} days of metrics"
            )
            continue
        peak_mem = max(max_mem_days)
        rec_mem = recommend_res(mem_limit, mem_res, peak_mem)
        if rec_mem != mem_res:
            print(
                f"ADJUSTING {cluster_name}/{svc_name}/{cname} {mem_limit}/{mem_res}/{peak_mem} {mem_res} -> {rec_mem}"
            )
            cdef["memoryReservation"] = rec_mem
            changed = True
    if changed:
        return task_def
    return None


def go():
    req_days = int(os.environ.get("REQUIRE_STAT_DAYS", 7))
    consider_days = int(os.environ.get("CONSIDER_STAT_DAYS", 14))
    now = datetime.utcnow()
    start_time = now - timedelta(days=consider_days)
    for svc in candidate_services():
        new_task_def = adjusted_task_def(svc)
        if new_task_def:
            update_service(svc["clusterArn"], svc["serviceName"], new_task_def)


def lambda_handler(event, _):
    print("event:", event)
    go()


if __name__ == "__main__":
    go()
