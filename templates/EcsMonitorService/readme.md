# EcsMonitorService

Provides a metric for memory utilization of EC2-backed ECS containers. This
provides a significantly less expensive alternative to AWS' Container Insights
as it only gathers one metric per container.

The service operates as a small Docker image which runs on each node in the ECS
cluster.

**See Also:** [sigcorp/ecs_monitor on DockerHub](https://hub.docker.com/r/sigcorp/ecs_monitor)
## Parameters

- `ClusterArn` (String) - **required** - Name or ARN of the cluster to monitor

- `Debug` (String) - Set to `yes` to enable debugging
  - **Default:** ``

- `DockerImage` (String) - Docker image to deploy.
  - **Default:** `sigcorp/ecs_monitor:0.1.10`

