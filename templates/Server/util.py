import sys
import hashlib
import os
from troposphere import AWSObject, Export, Output, Parameter, Ref, Template


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


def read_local_file(path):
    with open(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), path), "r"
    ) as fp:
        return fp.read()


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


def read_resource(path):
    return read_local_file(os.path.join("resources", path))


def md5(s):
    return hashlib.md5(s.encode("utf-8")).hexdigest()
