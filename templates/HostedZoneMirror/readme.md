## Parameters

- `LogRetentionDays` (Number) - Number of days to retain logs for the mirroring state machine
  - **Default:** `7`

- `MirrorConfig` (String) - **required** - JSON string with configuration for the mirroring process.

Example:
  {
    "sourceRoleName": "Route53MirrorRole",
    "zones": [
      {
        "sourceHostedZoneId": "Z02694372FYKFHNXABC123",
        "sourceAccountId": "12768521234",
        "destHostedZoneId": "Z02174371I29AGNABC321"
      }
    ]
  }


- `ScheduleExpression` (String) - EventBridge cron expression for how often the mirroring should be performed
  - **Default:** `rate(10 minutes)`

