## Parameters

*This template does not require parameters.*

## sceptre_user_data

- `vpc_cidr` (string) - **required** - CIDR for the VPC

- `vpc_name` (string)

- `vpc_extra_opts` (Dict)

- `subnets` (List of [SubnetModel](#SubnetModel))

- `customer_gateway` ([CustomerGatewayModel](#CustomerGatewayModel))



### CustomerGatewayModel

- `amazon_asn` (integer)

- `ip_address` (string) - **required**

- `static_routes_only` (boolean) - **required**

- `tunnel_inside_cidr` (string)

- `static_route_cidrs` (List of string)

- `customer_asn` (integer)
  - **Default:** `65000`

- `vpn_type` (string)
  - **Default:** `ipsec.1`



### SubnetModel

- `name` (string) - **required**

- `kind` (string) - **required**

- `availability_zone` (string) - **required**

- `cidr` (string) - **required**

- `nat_eip_allocation_id` (string)

- `map_public_ip_on_launch` (boolean)
  - **Default:** `False`

