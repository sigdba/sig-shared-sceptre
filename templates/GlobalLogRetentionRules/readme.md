# GlobalLogRetentionRules

Creates an AWS Lambda function which runs on a schedule to set the retention of
CloudWatch log groups.

CloudWatch log groups are often created automatically and without a retention
period set. This leads to unwanted data being retained long past its usefulness
while increasing AWS costs. Use this stack in each active region to ensure
you're not paying for logs you don't want.

## Parameters

*This template does not require parameters.*

## sceptre_user_data

- `rules` (List of [RuleModel](#RuleModel)) - **required** - The set of rules to apply to log groups.
  - Rules are applied in the order specified until a matching rule is
               applied at which point processing continues with the next log
               group.

- `schedule` (string) - The schedule on which the rules will be evaluated.
  - **Default:** `rate(1 day)`
  - **See Also:** [Creating an Amazon EventBridge rule that runs on a schedule](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-create-rule-schedule.html)



### RuleModel

A rule has a single matching function and an optional action. If a log
group matches a rule without an action then it will not be modified and
further processing of that group will stop.

Available matching functions: `starts_with`, `contains`, `regex`

Available actions: `retain_days`

- `contains` (string) - Matches log groups whose names contain the given string.

- `override_retention` (boolean) - When `false` log groups which already have a retention
        set will not be modified. When `true` the previous setting will be
        overriden.
  - **Default:** `False`

- `regex` (string) - Matches log groups whose name matches the given regular expression.

- `retain_days` (integer) - Matching log groups will have their retention set to the given number of days.

- `starts_with` (string) - Matches log groups whose names start with the given string.

