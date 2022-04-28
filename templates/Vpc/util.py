import sys
from troposphere import Template, Parameter, Export, Output

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


def add_export(title, key, value, **kwargs):
    return TEMPLATE.add_output(Output(title, Value=value, Export=Export(key), **kwargs))


def add_param(name, **kwargs):
    return TEMPLATE.add_parameter(Parameter(name, **kwargs))


def debug(*args):
    print(*args, file=sys.stderr)


def dashed_to_camel_case(t):
    return "".join([s[0].upper() + s[1:] for s in t.split("-")])


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
