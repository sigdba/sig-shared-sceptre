# EcsMemAutoTune

Creates a Lambda function which runs on a specified schedule to analyze the
memory used by ECS containers and tune their memory reservation to match
real-world usage.

**Important Note:** This stack relies on metrics gathered by [EcsMonitorService](../EcsMonitorService/readme.md).

## Parameters

- `ActiveServicesOnly` (String) - When 'true' only active services will be adjusted.
  - **Default:** `false`

- `ConsiderStatDays` (Number) - Number of days worth of memory statistics used to compute peak usage.
  - **Default:** `14`

- `DryRun` (String) - When 'true' memory adjustments will be reported but not executed.
  - **Default:** `false`

- `EcsClusters` (String) - **required** - Comma separated list of ECS Cluster names or ARNs. If 'ALL' then all clusters in the region will be included.

- `EnablingTag` (String) - Specifies a tag which may be set on services to control if they will be
adjusted. If the tag is present and set to 'true' then the service will be
adjusted. Any other value will be treated as false. If the tag is not
present then adjustment will depend on the RequireOptIn parameter.

  - **Default:** `AutoAdjustMemoryReservation`

- `MaxOverheadMb` (String) - Maximum amount to add to peak usage.
  - **Default:** ``

- `MinChangeMb` (Number) - Minimum downward change to trigger an adjustment. Upward adjustments will always be made.
  - **Default:** `64`

- `MinOverheadMb` (Number) - Minimum amount to add to peak usage.
  - **Default:** `1`

- `OverheadPct` (Number) - Percentage of peak usage to add.
  - **Default:** `0`

- `PassRoleExpr` (String) - **required** - Expression as used in a 'Resource' clause of an IAM statement. This limits
the set of roles the Lambda function is allowed to pass to services it's
adjusting. Example:
"arn:aws:iam::803071473383:role/sig-ban-ecs-*-TaskExecutionRole-*"


- `RequireOptIn` (String) - When 'true' only services with their EnablingTag set to 'true' will be
adjusted. When 'false' any service without the EnablingTag set will be
adjusted.

  - **Default:** `true`

- `RequiredStatDays` (Number) - Number of days worth of stats required to compute peak usage. A service
must have at least this mean days of statistics within the window set by
ConsiderStatDays. Services with fewer days of stats will not be adjusted.

  - **Default:** `7`

- `ScheduleExpression` (String) - **required** - cron-style expression indicating when the Lambda is run.

