## Parameters

- `DestAccountId` (String) - **required** - Account ID where records will be mirrored to

- `DomainName` (String) - Domain name of the hosted zone. Leave blank to omit.
  - **Default:** ``

- `RoleName` (String) - Name of the role to be assumed by the mirroring process.
  - **Default:** `Route53MirrorRole`

- `VpcId` (AWS::EC2::VPC::Id) - **required** - VPC where the private zone will be created

