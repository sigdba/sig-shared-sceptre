import yaml_doc

from os.path import dirname, basename
from jinja2 import Environment, FileSystemLoader, select_autoescape


def render_yamlj2(out_path, template):
    env = Environment(
        loader=FileSystemLoader(dirname(template)), autoescape=select_autoescape()
    )
    template = env.get_template(basename(template))
    yaml_doc.render_yaml_string(out_path, template.render())
