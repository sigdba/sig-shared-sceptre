import yaml

from render import render_field


class SafeLoaderIgnoreUnknown(yaml.SafeLoader):
    def ignore_unknown(self, node):
        return None


SafeLoaderIgnoreUnknown.add_constructor(None, SafeLoaderIgnoreUnknown.ignore_unknown)


def render_parameter(fp, param):
    render_field(fp, **param, required="Default" not in param)


def render_parameters(fp, root):
    params = root.get("Parameters", {})
    if len(params) < 1:
        return

    fp.write("## Parameters\n\n")
    keys = [k for k in params]
    keys.sort()
    for k in keys:
        render_parameter(fp, {**params[k], "title": k})


def render_yaml(out_path, template):
    with open(template, "r") as fp:
        root = yaml.load(fp, Loader=SafeLoaderIgnoreUnknown)

    with open(out_path, "w") as fp:
        render_parameters(fp, root)
