# Vpc

Creates a VPC, its subnets, and optional customer gateway (site-to-site VPN).

## Parameters

*This template does not require parameters.*

## sceptre_user_data

- `customer_gateway` ([CustomerGatewayModel](#CustomerGatewayModel))

- `subnets` (List of [SubnetModel](#SubnetModel))

- `vpc_cidr` (string) - **required** - CIDR for the VPC

- `vpc_extra_opts` (Dict)

- `vpc_name` (string)



### CustomerGatewayModel

- `amazon_asn` (integer)

- `customer_asn` (integer)
  - **Default:** `65000`

- `ip_address` (string) - **required**

- `static_route_cidrs` (List of string)

- `static_routes_only` (boolean) - **required**

- `tunnel_inside_cidr` (string)

- `vpn_type` (string)
  - **Default:** `ipsec.1`



### SubnetModel

- `availability_zone` (string) - **required**

- `cidr` (string) - **required**

- `kind` (string) - **required**

- `map_public_ip_on_launch` (boolean)
  - **Default:** `False`

- `name` (string) - **required**

- `nat_eip_allocation_id` (string)

