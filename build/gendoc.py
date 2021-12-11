#!/usr/bin/env python3
import importlib.machinery
import importlib.util
import inspect
import json
import sys
import os.path
from pydantic import BaseModel
from pydantic.schema import schema
from troposphere import Template


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
    return dict(
        inspect.getmembers(
            module, lambda c: inspect.isclass(c) and issubclass(c, BaseModel)
        )
    )


def get_schema(model_classes):
    if TOP_MODEL not in model_classes:
        raise ValueError("Top-level model class not found: %s" % TOP_MODEL)
    top_class = model_classes[TOP_MODEL]
    return schema([top_class], ref_template="{model}")


def is_ref(r):
    return type(r) is dict and "$ref" in r


def ref_type_of_def(r):
    if is_ref(r):
        return r["$ref"]
    if not type(r) is dict:
        return None
    if "items" in r:
        return ref_type_of_def(r["items"])
    if "allOf" in r:
        ao = r["allOf"]
        if len(ao) != 1:
            raise ValueError("don't know what to do with allOf: %s" % ao)
        return ref_type_of_def(ao[0])
    return None


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
        queue = [
            (q, indent_level + 1)
            for q in [ref_type_of_def(r) for r in d["properties"].values()]
            if q
        ] + queue


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


def field_default_str(field):
    if field.get("omit_default", False):
        return None
    desc = field.get("default_description", None)
    if desc is not None:
        return desc
    val = field.get("default", None)
    if val is not None:
        if val == [] or val == {}:
            return None
        return f"`{val}`"
    return None


def render_field(fp, spec={}, **kwargs):
    field = {**spec, **{k.lower(): v for k, v in kwargs.items()}}
    req = " - **required**" if "required" in field and field["required"] else ""
    fp.write("- `{}` ({}){}".format(field["title"], field["type"], req))

    if "description" in field and field["description"]:
        fp.write(" - ")
        fp.write(field["description"])
    fp.write("\n")

    default = field_default_str(field)
    if default:
        fp.write(f"  - **Default:** {default}\n")

    for note in field.get("notes", []):
        fp.write(f"  - {note}\n")

    fp.write("\n")


def render_parameter(fp, param):
    render_field(fp, **param, required="Default" not in param)


def render_parameters(fp, module):
    fp.write("## Parameters\n\n")
    for p in get_parameters_in_order(module):
        render_parameter(fp, p)


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
    for k, v in sdef["properties"].items():
        render_schema_prop(fp, k, {"required": k in required, **v})


def render_schema_defs(fp, schema):
    for d in get_schema_defs_in_order(schema):
        render_schema_def(fp, d)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate documentation for Pydantic-based Sceptre templates"
    )
    parser.add_argument("template", help="path to Python 3 template file")
    parser.add_argument("output", help="path to output file")

    args = parser.parse_args()

    module = load_template_module(args.template)
    model_classes = get_model_classes(module)
    schema = get_schema(model_classes)

    with open(args.output, "w") as fp:
        render_parameters(fp, module)
        render_schema_defs(fp, schema)
