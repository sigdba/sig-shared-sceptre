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


def field_requirement_str(field):
    req = field.get("requirement_description", None)
    if req:
        return f" - **{req}**"
    if field.get("required", False):
        return " - **required**"
    return ""


def render_field(fp, spec={}, **kwargs):
    field = {**spec, **{k.lower(): v for k, v in kwargs.items()}}
    req = field_requirement_str(field)
    fp.write("- `{}` ({}){}".format(field["title"], field["type"], req))

    if "description" in field and field["description"]:
        fp.write(" - ")
        fp.write(field["description"])
    fp.write("\n")

    allowed = field.get("enum")
    if allowed:
        allowed = ", ".join(map(lambda v: f"`{v}`", allowed))
        fp.write(f"  - **Allowed Values:** {allowed}\n")

    default = field_default_str(field)
    if default:
        fp.write(f"  - **Default:** {default}\n")

    for note in field.get("notes", []):
        fp.write(f"  - {note}\n")

    fp.write("\n")
