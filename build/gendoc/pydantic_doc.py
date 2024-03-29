import importlib.machinery
import importlib.util
import inspect
import os.path
import sys
import types

from pydantic import BaseModel
from pydantic.schema import schema
from troposphere import Template

from gd_util import flatten
from render import render_field


TOP_MODEL = "UserDataModel"


def load_template_module(path):
    sys.path.insert(0, os.path.dirname(path))
    name = os.path.splitext(os.path.basename(path))[0]
    loader = importlib.machinery.SourceFileLoader(name, path)
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def get_model_classes(module):
    # First check for a standard import of a model module (as opposed to a
    # star-import)
    sub_modules = dict(
        inspect.getmembers(module, lambda c: isinstance(c, types.ModuleType))
    )
    ret = get_model_classes(sub_modules["model"]) if "model" in sub_modules else {}
    return {
        **ret,
        **dict(
            inspect.getmembers(
                module, lambda c: inspect.isclass(c) and issubclass(c, BaseModel)
            )
        ),
    }


class TopLevelModelNotFoundError(Exception):
    pass


def get_schema(model_classes):
    if TOP_MODEL not in model_classes:
        raise TopLevelModelNotFoundError(
            "Top-level model class not found: %s" % TOP_MODEL
        )
    top_class = model_classes[TOP_MODEL]
    return schema([top_class], ref_template="{model}")


def is_ref(r):
    return type(r) is dict and "$ref" in r


def ref_types_of_def(r):
    if is_ref(r):
        return [r["$ref"]]
    if type(r) is list:
        return flatten([ref_types_of_def(i) for i in r])
    if not type(r) is dict:
        return []
    if "items" in r:
        return ref_types_of_def(r["items"])
    if "allOf" or "anyOf" in r:
        return flatten([ref_types_of_def(r.get(k, [])) for k in ["allOf", "anyOf"]])
    return []


def get_schema_defs_in_order(schema):
    defs = schema["definitions"]
    queue = [(TOP_MODEL, 0)]  # tuple of model name and indent level
    done = []
    while len(queue) > 0:
        name, indent_level = queue.pop(0)
        if name in done:
            continue
        done.append(name)
        d = defs[name]
        yield {**d, "indent_level": indent_level}
        for prop_val in d["properties"].values():
            for rt in ref_types_of_def(prop_val):
                queue.insert(0, (rt, indent_level + 1))


def get_parameters(module):
    try:
        template = module.sceptre_handler(None)
        if type(template) is dict:
            return template.get("Parameters", {})
        elif type(template) is Template:
            return template.to_dict().get("Parameters", {})
        else:
            print(
                "WARNING: Calling scepture_handler() with None returned a non-dict:\n",
                template,
            )
            return {}
    except Exception as e:
        print("WARNING: Error when calling sceptre_handler() with None:\n", e)
        return {}


def get_parameters_in_order(module):
    params = get_parameters(module)
    keys = [k for k in params]
    keys.sort()
    return [{**params[k], "title": k} for k in keys]


def render_parameter(fp, param):
    render_field(fp, **param, required="Default" not in param)


def render_parameters(fp, module):
    fp.write("## Parameters\n\n")
    has_params = False
    for p in get_parameters_in_order(module):
        has_params = True
        render_parameter(fp, p)
    if not has_params:
        fp.write("*This template does not require parameters.*")


def schema_prop_type_str(p):
    if is_ref(p):
        return f"[{p['$ref']}](#{p['$ref']})"
    if "anyOf" in p:
        return " or ".join([schema_prop_type_str(o) for o in p["anyOf"]])
    if "items" in p:
        items = p["items"]
        if items == {}:
            return "List"
        return "List of " + schema_prop_type_str({"allOf": [items]})
    if "allOf" in p:
        return schema_prop_type_str({"anyOf": p["allOf"]})
    if p["type"] == "object":
        v_type = p.get("additionalProperties", {}).get("type", None)
        if v_type:
            return f"Dict[string:{v_type}]"
        return "Dict"
    return p["type"]


def schema_prop_default_str(p):
    return p.get("default", None)


def render_schema_prop(fp, name, prop):
    try:
        render_field(
            fp,
            prop,
            title=name,
            type=schema_prop_type_str(prop),
            default=schema_prop_default_str(prop),
        )
    except Exception as e:
        print(f"Error rendering schema prop '{name}':{prop}")
        raise e


def render_schema_def(fp, sdef):
    heading_leader = "#" * (2 + sdef["indent_level"])
    title = sdef["title"]
    title = "sceptre_user_data" if title == TOP_MODEL else title
    fp.write(f"\n\n{heading_leader} {title}\n\n")

    desc = sdef.get("description", None)
    if desc:
        fp.write(f"{desc}\n\n")

    required = sdef.get("required", [])
    for k, v in sorted(sdef["properties"].items()):
        render_schema_prop(fp, k, {"required": k in required, **v})


def render_schema_defs(fp, schema):
    for d in get_schema_defs_in_order(schema):
        render_schema_def(fp, d)


def render_python(out_path, template):
    try:
        module = load_template_module(template)
        model_classes = get_model_classes(module)
        model_schema = get_schema(model_classes)
    except TopLevelModelNotFoundError:
        print("WARNING: Pydantic UserDataModel not found:", template)
        return

    # print(yaml.dump(schema))
    with open(out_path, "w") as fp:
        render_parameters(fp, module)
        render_schema_defs(fp, model_schema)
