import sys
from troposphere import Template, Parameter, AWSObject, Ref

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

    return {k: _eval(v) for k, v in kwargs.items() if v is not None}


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
