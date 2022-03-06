## Parameters



## sceptre_user_data

- `vpc_cidr` (string) - **required**

- `vpc_name` (string)

- `vpc_extra_opts` (Dict)

- `subnets` (List of [SubnetModel](#SubnetModel))



### SubnetModel

- `name` (string) - **required**

- `kind` (string) - **required**

- `availability_zone` (string) - **required**

- `cidr` (string) - **required**

- `nat_eip_allocation_id` (string)

- `map_public_ip_on_launch` (boolean)
  - **Default:** `False`

