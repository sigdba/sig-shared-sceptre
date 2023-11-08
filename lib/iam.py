from typing import Union, Set, Optional, List, Iterable

from troposphere import Base64, GetAtt, Ref, Sub, Tags
from troposphere.autoscaling import (
    AutoScalingGroup,
    LaunchConfiguration,
    LifecycleHook,
    MetricsCollection,
    NotificationConfigurations,
)
from troposphere.iam import InstanceProfile, Policy, Role
from troposphere.stepfunctions import StateMachine

from util import (
    TEMPLATE,
    md5,
    add_export,
    add_param,
    add_resource,
    add_resource_once,
    opts_with,
    read_resource,
)

AUTOSCALING_SERVICE = "autoscaling.amazonaws.com"
EVENTS_SERVICE = "events.amazonaws.com"
PIPES_SERVICE = "pipes.amazonaws.com"
STATES_SERVICE = "states.amazonaws.com"


def statement(
    action: Union[str, Iterable[str]],
    resource: Union[str, Iterable[str]],
    effect: Union[str, Iterable[str]] = "Allow",
) -> dict:
    def inline(v):
        if isinstance(v, str):
            return v
        return list(v)

    return {
        "Effect": inline(effect),
        "Action": inline(action),
        "Resource": inline(resource),
    }


OneOrMoreStrings = Union[str, Iterable[str], Ref, GetAtt]


def _as_unique_list(x: OneOrMoreStrings) -> Set[str]:
    if isinstance(x, str) or isinstance(x, Ref) or isinstance(x, GetAtt):
        return {x}
    return list(set(x))


def policy(
    name: Optional[str] = None,
    version: str = "2012-10-17",
    statements: Set[dict] = [],
    allow: dict[OneOrMoreStrings, OneOrMoreStrings] = {},
    deny: dict[OneOrMoreStrings, OneOrMoreStrings] = {},
) -> Policy:
    def _statement_gen(
        effect: str, d: dict[OneOrMoreStrings, OneOrMoreStrings]
    ) -> Iterable[dict]:
        for actions, resources in d.items():
            yield statement(
                _as_unique_list(actions), _as_unique_list(resources), effect
            )

    statements = (
        statements
        + list(_statement_gen("Allow", allow))
        + list(_statement_gen("Deny", deny))
    )

    return Policy(
        PolicyName=name or md5(statements),
        PolicyDocument={
            "Version": version,
            "Statement": statements,
        },
    )


def role(
    name: str,
    policies: Iterable[Policy] = [],
    allow: dict[OneOrMoreStrings, OneOrMoreStrings] = {},
    deny: dict[OneOrMoreStrings, OneOrMoreStrings] = {},
    allow_assume: Optional[Iterable[str]] = None,
    managed_policy_arns: Iterable[str] = [],
    path: str = "/",
) -> Role:
    if len(allow) + len(deny) > 0:
        policies = list(policies) + [policy("inline", allow=allow, deny=deny)]
    return Role(
        name,
        Policies=list(policies),
        ManagedPolicyArns=list(managed_policy_arns),
        Path=path,
        **opts_with(
            AssumeRolePolicyDocument=(
                allow_assume,
                lambda services: {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": {"Service": services},
                            "Action": ["sts:AssumeRole"],
                        }
                    ],
                },
            )
        )
    )
