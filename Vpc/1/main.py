import hashlib
import os.path

from troposphere import Ref, Sub, GetAtt, Tags, Tag
from troposphere.ec2 import (
    VPC,
    Subnet,
    InternetGateway,
    NatGateway,
    VPCGatewayAttachment,
    RouteTable,
    Route,
    SubnetRouteTableAssociation,
    EIP,
)

from model import *
from util import *

public_subnets_models_by_az = {}


def r_vpc(user_data):
    name = user_data.vpc_name if user_data.vpc_name else Ref("AWS::StackName")
    return add_resource(
        VPC(
            "Vpc",
            CidrBlock=user_data.vpc_cidr,
            EnableDnsSupport=True,
            Tags=[Tag("Name", name)],
        )
    )


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
        if not az in public_subnets_models_by_az:
            raise ValueError(
                f"No public subnet defined in {subnet_model.availability_zone}"
            )
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
        clean_title(f"EXPORT{subnet_model.name}"),
        Sub("${AWS::StackName}-" + subnet_model.name + "-subnetId"),
        Ref(ret),
    )

    return ret


def subnets(models):
    # Public subnets need to be defined first so that NATs can be built in them
    # which are then used by the private subnets.
    publics = [connected_subnet(s) for s in models if s.kind == "public"]
    privates = [connected_subnet(s) for s in models if s.kind != "public"]
    return publics + privates


def sceptre_handler(sceptre_user_data):
    user_data = UserDataModel(**sceptre_user_data)

    r_vpc(user_data)
    subnets(user_data.subnets)

    return TEMPLATE.to_json()
