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

- `routes` (List of [RouteModel](#RouteModel))



#### RouteModel

- `carrier_gateway_id` (string) - The ID of the carrier gateway.

- `dest_cidr` (string) - **required** - The IPv4 CIDR block used for the destination match.

- `eggress_only_internet_gateway_id` (string) - The ID of the egress-only internet gateway.

- `gateway_id` (string) - The ID of an internet gateway or virtual private gateway attached to your VPC.

- `instance_id` (string) - The ID of a NAT instance in your VPC.

- `local_gateway_id` (string) - The ID of the local gateway.

- `nat_gateway_id` (string) - The ID of a NAT gateway.

- `network_interface_id` (string) - The ID of the network interface.

- `transit_gateway_id` (string) - The ID of a transit gateway.

- `vpc_endpoint_id` (string) - The ID of a VPC endpoint. Supported for Gateway Load Balancer endpoints only.

- `vpc_peering_connection_id` (string) - The ID of a VPC peering connection.

