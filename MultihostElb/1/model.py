from typing import List, Optional, Dict
from pydantic import BaseModel, ValidationError, validator, root_validator

from util import *

#
# IMPORTANT: The following classes are DATA CLASSES using pydantic.
#            DO NOT add behavior to them beyond input validation. Use functions
#            instead.
#


class RetainInputsModel(BaseModel):
    input_values = {}

    @root_validator(pre=True)
    def store_input_values(cls, values):
        return {**values, "input_values": values}


class HostnameModel(BaseModel):
    hostname: str
    certificate_arn: Optional[str]


class RedirectModel(BaseModel):
    host: Optional[str]
    path: Optional[str]
    port: Optional[int]
    protocol: Optional[str]
    query: Optional[str]
    status_code = 302

    @validator("protocol")
    def check_protocol(cls, v):
        return model_limit_values(["HTTP", "HTTPS", "#{protocol}"], v)

    @validator("status_code")
    def check_status_code(cls, v):
        return model_limit_values([301, 302], v)


class TargetModel(BaseModel):
    id: str
    port: Optional[int]


class HealthCheckModel(BaseModel):
    interval_seconds: Optional[int]
    path: Optional[str]
    timeout_seconds: Optional[int]
    interval_seconds: Optional[int]
    protocol: Optional[str]
    healthy_threshold_count: Optional[int]
    unhealth_threshold_count: Optional[int]


class FixedResponseModel(BaseModel):
    message_body: Optional[str]
    content_type = "text/plain"
    status_code = 200

    @validator("content_type")
    def check_content_type(cls, v):
        return model_limit_values(
            [
                "text/plain",
                "text/css",
                "text/html",
                "application/javascript",
                "application/json",
            ],
            v,
        )


class ActionModel(BaseModel):
    fixed_response: Optional[FixedResponseModel]
    health_check: Optional[HealthCheckModel]
    redirect: Optional[RedirectModel]
    target_port = 8080
    target_protocol = "HTTP"
    target_group_attributes: Dict[str, str] = {}
    targets: List[TargetModel] = []

    @validator("target_group_attributes", always=True)
    def include_defaults_in_target_group_attributes(cls, v):
        return {**{"stickiness.enabled": "true", "stickiness.type": "lb_cookie"}, **v}

    @validator("target_protocol")
    def check_target_protocol(cls, v):
        return model_limit_values(["HTTP", "HTTPS"], v)

    @validator("targets", pre=True, each_item=True)
    def coerce_targets(cls, v):
        if isinstance(v, str):
            return TargetModel(id=v)
        return v


class QueryStringMatchModel(BaseModel):
    key: str
    value: str


class RuleModel(RetainInputsModel, ActionModel):
    paths: List[str] = []
    hosts: List[str] = []
    match_query_string: List[QueryStringMatchModel] = []
    priority: Optional[int]
    # TODO: Document priority

    @root_validator(pre=True)
    def path_alias(cls, values):
        return model_string_or_list("paths", model_alias("paths", "path", values))

    @root_validator(pre=True)
    def host_alias(cls, values):
        return model_string_or_list("hosts", model_alias("hosts", "host", values))

    @root_validator()
    def require_hosts_or_paths(cls, values):
        if len(values["hosts"]) < 1 and len(values["paths"]) < 1:
            raise ValueError("one of hosts or paths must be specified")
        return values


class ListenerModel(BaseModel):
    hostnames: List[HostnameModel] = []
    protocol: str
    port: int
    default_action = ActionModel()
    https_redirect_to: Optional[int]
    rules: List[RuleModel] = []

    @root_validator(pre=True)
    def detect_protocol(cls, values):
        if "protocol" not in values:
            port = values["port"]
            if port == 80:
                values["protocol"] = "HTTP"
            elif port == 443:
                values["protocol"] = "HTTPS"
            else:
                raise ValueError(
                    "You must specify a protocol for listener on non-standard port: {}".format(
                        port
                    )
                )
        return values

    @validator("hostnames", pre=True, each_item=True)
    def coerce_hostnames(cls, v):
        if isinstance(v, str):
            return HostnameModel(hostname=v)
        return v

    @root_validator
    def require_hostnames_for_https(cls, values):
        if values["protocol"] == "HTTPS" and (
            "hostnames" not in values or len(values["hostnames"]) < 1
        ):
            raise ValueError("hostnames key is required for HTTPS listeners")
        return values


class NsUpdateModel(BaseModel):
    lambda_arn: Optional[str]
    lambda_arn_export_name: Optional[str]
    lambda_props: Dict[str, str] = {}
    lambda_record_type_key = "RecordType"
    lambda_record_key: str
    lambda_zone_key: str
    lambda_value_key = "Value"
    zone_splits_at = 1

    @root_validator()
    def require_lambda_arn_or_export(cls, values):
        if "lambda_arn" not in values and "lambda_arn_export_name" not in values:
            raise ValueError(
                "one of lambda_arn or lambda_arn_export_name must be specified"
            )
        return values


class AccessLogsModel(BaseModel):
    enabled = True
    retain_days = 90
    prefix_expr = "${AWS::StackName}-access."
    bucket: Optional[str]


class UserDataModel(BaseModel):
    name = "${AWS::StackName}"
    listeners: List[ListenerModel]
    subnet_ids: List[str]
    domain: Optional[str]
    internet_facing: bool
    access_logs: Optional[AccessLogsModel]
    allow_cidrs: Optional[List[str]]
    attributes: Dict[str, str] = {}
    certificate_validation_method = "DNS"
    elb_security_groups: List[str] = []
    elb_tags: Dict[str, str] = {}
    hosted_zone_id: Optional[str]
    ns_update: Optional[NsUpdateModel]

    @root_validator
    def require_listeners(cls, values):
        if len(values["listeners"]) < 1:
            raise ValueError("at least one listener is required")
        return values

    @root_validator
    def require_subnet_ids(cls, values):
        if len(values["subnet_ids"]) < 2:
            raise ValueError("at least two subnet_ids are required")
        return values
