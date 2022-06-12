## Parameters

- `AdminGroupName` (String) - If `CreateAdminGroup` is `true`, this will be the name of the group.
  - **Default:** `AdminsWithMfa`

- `AdminGroupPath` (String) - If `CreateAdminGroup` is `true`, this will be the path to the group.
  - **Default:** `/`

- `CreateAdminGroup` (String) - When `true` an IAM group will be created whose members are granted full
administrative access but require MFA-authenticated requests.

  - **Default:** `true`

- `PolicyName` (String) - Name of the policy which will deny requests not authenticated with MFA
  - **Default:** `RequireMFA`

