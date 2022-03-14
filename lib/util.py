import sys
import hashlib
import os.path
from troposphere import Template, Parameter, AWSObject, Ref, Output, Export

TEMPLATE = Template()

TITLE_CHAR_MAP = {
    "-": "DASH",
    ".": "DOT",
    "_": "US",
    "*": "STAR",
    "?": "QM",
    "/": "SLASH",
    " ": "SP",
}


def add_resource(r):
    TEMPLATE.add_resource(r)
    return r


def add_resource_once(logical_id, res_fn):
    res = TEMPLATE.to_dict()["Resources"]
    if logical_id in res:
        return res[logical_id]
    else:
        return add_resource(res_fn(logical_id))


def clean_title(s):
    for k in TITLE_CHAR_MAP.keys():
        s = s.replace(k, TITLE_CHAR_MAP[k])
    return s


def add_param(name, **kwargs):
    return TEMPLATE.add_parameter(Parameter(name, **kwargs))


def add_output(title, value, export_name=None, **kwargs):
    return TEMPLATE.add_output(
        Output(title, Value=value, **opts_with(Export=(export_name, Export)), **kwargs)
    )


def add_export(title, key, value, **kwargs):
    add_output(title, value, key, **kwargs)


def add_mapping(name, mapping):
    return TEMPLATE.add_mapping(name, mapping)


def debug(*args):
    print(*args, file=sys.stderr)


def tags_with(tags, tags_key="Tags"):
    if type(tags) is dict:
        tags = [{"Key": k, "Value": v} for k, v in tags.items()]
    if len(tags) < 1:
        return {}
    return {tags_key: tags}


def opts_with(**kwargs):
    def _eval(v):
        if type(v) is tuple:
            val, fn, *args = v
            return _eval(fn(*args, val))
        if isinstance(v, AWSObject):
            return Ref(v)
        return v

    def has_value(v):
        if type(v) is tuple:
            return v[0] is not None
        return v is not None

    return {k: _eval(v) for k, v in kwargs.items() if has_value(v)}


def opts_from(o, **kwargs):
    d = dict(o)
    return {k: d[v] for k, v in kwargs.items() if d[v]}


def troposphere_opt(cls, k, v):
    # TODO: Make this recursive
    if "props" not in dir(cls) or k not in cls.props:
        return v
    typ = cls.props[k][0]
    if type(typ) is list:
        return [typ[0](**i) for i in v]
    return typ(**v)


def troposphere_opts(cls, **kwargs):
    return {k: troposphere_opt(cls, k, v) for k, v in kwargs.items()}


def flatten(lst):
    def f(v):
        queue = v
        while len(queue) > 0:
            item = queue.pop(0)
            if type(item) is list:
                queue.extend(item)
            else:
                yield item

    return list(f(lst))


def read_local_file(path):
    with open(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), path), "r"
    ) as fp:
        return fp.read()


def read_resource(path):
    return read_local_file(os.path.join("resources", path))


def model_alias(keeper, alias, values):
    if alias in values:
        if keeper in values:
            raise ValueError(
                "{} is an alias for {}, they cannot be specified together".format(
                    alias, keeper
                )
            )
        values[keeper] = values[alias]
        del values[alias]
    return values


def model_string_or_list(key, values):
    if key in values:
        v = values[key]
        if isinstance(v, str):
            values[key] = [v]
    return values


def model_limit_values(allowed, v):
    if v not in allowed:
        raise ValueError("value must be one of {}", allowed)
    return v


def model_exclusive(values, *keys, required=False):
    has = [k for k in keys if k in values and values[k] is not None]
    if len(has) < 1:
        if required:
            raise ValueError(f"One of {', '.join(keys)} must be specified.")
        return None
    if len(has) > 1:
        raise ValueError(f"Only one of {', '.join(keys)} may be specified.")
    return has[0]


def md5(*s):
    hs = "".join(map(str, s))
    return hashlib.md5(hs.encode("utf-8")).hexdigest()
