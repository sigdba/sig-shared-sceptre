from troposphere import Ref, Sub, GetAtt, Tags, Tag
from troposphere.ec2 import (
    VPC,
    Subnet,
    InternetGateway,
    NatGateway,
    CustomerGateway,
    VPNGateway,
    VPNConnection,
    VPCGatewayAttachment,
    VpnTunnelOptionsSpecification,
    RouteTable,
    Route,
    SubnetRouteTableAssociation,
    EIP,
)

import model
from util import (
    TEMPLATE,
    add_resource,
    add_resource_once,
    add_export,
    clean_title,
    opts_with,
    dashed_to_camel_case,
)


public_subnets_models_by_az = {}


def r_vpc(user_data):
    name = user_data.vpc_name if user_data.vpc_name else Ref("AWS::StackName")
    ret = add_resource(
        VPC(
            "Vpc",
            CidrBlock=user_data.vpc_cidr,
            EnableDnsSupport=True,
            Tags=[Tag("Name", name)],
            **user_data.vpc_extra_opts,
        )
    )
    add_export("VpcId", Sub("${AWS::StackName}-vpcId"), Ref(ret))
    add_export("VpcCidr", Sub("${AWS::StackName}-cidr"), user_data.vpc_cidr)
    return ret


def igw():
    ret = add_resource_once(
        "Igw", lambda n: InternetGateway(n, Tags=[Tag("Name", Ref("AWS::StackName"))])
    )
    add_resource_once(
        "IgwAttach",
        lambda n: VPCGatewayAttachment(
            n, InternetGatewayId=Ref("Igw"), VpcId=Ref("Vpc")
        ),
    )
    return ret


def nat_gateway(az):
    def add_nat(name):
        if az not in public_subnets_models_by_az:
            raise ValueError(f"No public subnet defined in {az}")
        sn, sn_model = public_subnets_models_by_az[az]
        if sn_model.nat_eip_allocation_id:
            alloc_id = sn_model.nat_eip_allocation_id
        else:
            alloc_id = GetAtt(
                add_resource(
                    EIP(
                        clean_title(f"NatEIP{az}"),
                        Domain="vpc",
                        Tags=Tags(Name=Sub("${AWS::StackName}-NAT-" + az)),
                    )
                ),
                "AllocationId",
            )
        return NatGateway(
            clean_title(name),
            AllocationId=alloc_id,
            ConnectivityType="public",
            SubnetId=Ref(sn),
            Tags=Tags(Name=Sub("${AWS::StackName}-" + az)),
        )

    return add_resource_once(clean_title(f"NatGatewayIN{az}"), add_nat)


def subnet(subnet_model):
    ret = add_resource(
        Subnet(
            clean_title(f"SUBNET{subnet_model.name}"),
            AvailabilityZone=subnet_model.availability_zone,
            CidrBlock=subnet_model.cidr,
            MapPublicIpOnLaunch=subnet_model.map_public_ip_on_launch,
            VpcId=Ref("Vpc"),
            Tags=[Tag("Name", Sub("${AWS::StackName}-" + subnet_model.name))],
        )
    )
    return ret


# Returns a route table with a default route. The kwargs is passed to the
# default route's constructor.
def add_route_table(subnet, name, **kwargs):
    title = clean_title(name)
    rt = add_resource(
        RouteTable(
            f"RouteTable{title}",
            Tags=[Tag("Name", Sub("${AWS::StackName}-" + name))],
            VpcId=Ref("Vpc"),
        )
    )

    add_resource(
        SubnetRouteTableAssociation(
            f"RouteTableAssoc{title}",
            RouteTableId=Ref(rt),
            SubnetId=Ref(subnet),
        )
    )

    add_resource(
        Route(
            f"DefaultRoute{title}",
            RouteTableId=Ref(rt),
            DestinationCidrBlock="0.0.0.0/0",
            **kwargs,
        )
    )

    return rt


def connected_subnet(subnet_model):
    ret = subnet(subnet_model)

    if subnet_model.kind == "public":
        public_subnets_models_by_az[subnet_model.availability_zone] = (
            ret,
            subnet_model,
        )
        igw()
        add_route_table(ret, subnet_model.name, GatewayId=Ref("Igw"))
    elif subnet_model.kind == "private":
        add_route_table(
            ret,
            subnet_model.name,
            NatGatewayId=Ref(nat_gateway(subnet_model.availability_zone)),
        )
    else:
        raise ValueError(f"Unknown subnet kind: {subnet_model.kind}")

    add_export(
        dashed_to_camel_case(subnet_model.name) + "SubnetId",
        Sub("${AWS::StackName}-" + subnet_model.name + "-subnetId"),
        Ref(ret),
    )
    add_export(
        dashed_to_camel_case(subnet_model.name) + "Cidr",
        Sub("${AWS::StackName}-" + subnet_model.name + "-cidr"),
        subnet_model.cidr,
    )

    return ret


def subnets(models):
    # Public subnets need to be defined first so that NATs can be built in them
    # which are then used by the private subnets.
    publics = [connected_subnet(s) for s in models if s.kind == "public"]
    privates = [connected_subnet(s) for s in models if s.kind != "public"]
    return publics + privates


def customer_gateway(gw_model):
    return add_resource(
        CustomerGateway(
            "CustomerGateway",
            BgpAsn=gw_model.customer_asn,
            IpAddress=gw_model.ip_address,
            Type=gw_model.vpn_type,
            Tags=Tags(Name=Ref("AWS::StackName")),
        )
    )


def vpn_gateway(gw_model):
    return add_resource(
        VPNGateway(
            "VpnGateway",
            Type=gw_model.vpn_type,
            Tags=Tags(Name=Ref("AWS::StackName")),
            **opts_with(AmazonSideAsn=gw_model.amazon_asn),
        )
    )


def attach_customer_gateway(gw_model):
    vpg = vpn_gateway(gw_model)

    vpn_conn = add_resource(
        VPNConnection(
            "CustomerGatewayConnection",
            CustomerGatewayId=Ref(customer_gateway(gw_model)),
            VpnGatewayId=Ref(vpg),
            Type=gw_model.vpn_type,
            StaticRoutesOnly=gw_model.static_routes_only,
            Tags=Tags(Name=Ref("AWS::StackName")),
            VpnTunnelOptionsSpecifications=[
                VpnTunnelOptionsSpecification(
                    **opts_with(TunnelInsideCidr=gw_model.tunnel_inside_cidr)
                )
            ],
        )
    )

    return add_resource(
        VPCGatewayAttachment(
            "CustomerGatewayAttachment", VpcId=Ref("Vpc"), VpnGatewayId=Ref(vpg)
        )
    )


def sceptre_handler(sceptre_user_data):
    if sceptre_user_data is None:
        # We're generating documetation. Return the template with just parameters.
        return TEMPLATE

    user_data = UserDataModel(**sceptre_user_data)

    r_vpc(user_data)
    subnets(user_data.subnets)

    if user_data.customer_gateway:
        attach_customer_gateway(user_data.customer_gateway)

    return TEMPLATE.to_json()
