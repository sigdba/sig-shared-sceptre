from typing import Dict, List, Optional, Union

from pydantic import BaseModel, Field, root_validator, validator
from troposphere import Ref, Sub, Tags
from troposphere.ec2 import SecurityGroup

from util import add_resource, flatten, opts_with

#
# IMPORTANT: The following classes are DATA CLASSES using pydantic.
#            DO NOT add behavior to them beyond input validation. Use functions
#            instead.
#


class SecurityGroupAllowModel(BaseModel):
    cidr: Union[str, List[str]] = Field(
        [],
        description="The IPv4 address range(s), in CIDR format. May be specified as a single string or a list of strings.",
        notes=["You must specify one of `cidr` or `sg_id` but not both."],
    )
    sg_id: Optional[str] = Field(
        description="The ID of a security group whose members are allowed.",
        notes=["You must specify one of `cidr` or `sg_id` but not both."],
    )
    sg_owner: Optional[str] = Field(
        description="The AWS account ID that owns the security group specified in `sg_id`. This value is required if the SG is in another account."
    )
    description: str
    protocol = "tcp"
    from_port: int
    to_port: int

    @root_validator(pre=True)
    def require_cidr_or_sg_id(cls, values):
        if "cidr" in values and values["cidr"] and len(values["cidr"]) > 0:
            if "sg_id" in values:
                raise ValueError("cidr and sg_id cannot be specified together")
        elif "sg_id" not in values:
            raise ValueError("one of cidr or sg_id must be specified")
        return values

    @validator("cidr")
    def make_cidr_a_list(cls, v):
        if type(v) is list:
            return v
        return [v]

    def parse_port(port):
        if isinstance(port, int):
            return (port, port)
        p = port.strip()
        if p == "any":
            return (-1, -1)
        elif p.isnumeric():
            return (int(p), int(p))
        elif "-" in p:
            lst = [s.strip() for s in p.split("-")]
            if len(lst) != 2 or not all(s.isnumeric() for s in lst):
                raise ValueError(f"Invalid port specification: '{port}'")
            return (int(lst[0]), int(lst[1]))
        raise ValueError(f"Invalid port specification: '{port}'")

    @root_validator(pre=True)
    def handle_port(cls, values):
        if "from_port" in values and "to_port" in values:
            if "port" in values:
                raise ValueError("port cannot be specified with from_ and to_port")
        elif "from_port" in values or "to_port" in values:
            raise ValueError("from_port and to_port must be specified together")
        elif "port" in values:
            f, t = cls.parse_port(values["port"])
            values["from_port"] = f
            values["to_port"] = t
            del values["port"]
        else:
            raise ValueError("Either port or from_ and to_port must be specified")

        return values


class SecurityGroupModel(BaseModel):
    egress: List[Dict[str, str]] = [
        {
            "CidrIp": "0.0.0.0/0",
            "Description": "Allow all outbound",
            "FromPort": "-1",
            "ToPort": "-1",
            "IpProtocol": "-1",
        }
    ]
    allow: List[Union[SecurityGroupAllowModel, List[SecurityGroupAllowModel]]] = []
    tags: Dict[str, str] = {}

    @validator("allow")
    def flatten_allow_list(cls, v):
        return flatten(v)


def ingress_for_allow(allow):
    base_opts = {
        "Description": allow.description,
        "FromPort": allow.from_port,
        "ToPort": allow.to_port,
        "IpProtocol": "-1" if allow.protocol == "any" else allow.protocol,
    }

    def gen():
        for cidr in allow.cidr:
            yield {**base_opts, "CidrIp": cidr}
        if allow.sg_id:
            yield {
                **base_opts,
                "SourceSecurityGroupId": allow.sg_id,
                **opts_with(SourceSecurityGroupOwnerId=allow.sg_owner),
            }

    return list(gen())


def security_group(
    title, model, description="${AWS::StackName}", name=None, vpc_id=None
):
    if not name:
        name = "${AWS::StackName}-" + title
    if not vpc_id:
        vpc_id = Ref("VpcId")
    return add_resource(
        SecurityGroup(
            "InstanceSg",
            GroupName=Sub(name),
            VpcId=vpc_id,
            GroupDescription=Sub(description),
            SecurityGroupEgress=model.egress,
            SecurityGroupIngress=[i for a in model.allow for i in ingress_for_allow(a)],
            Tags=Tags(Name=name, **model.tags),
        )
    )
