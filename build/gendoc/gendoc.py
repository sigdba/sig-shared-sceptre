#!/usr/bin/env python3

import pydantic_doc

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate documentation for Pydantic-based Sceptre templates"
    )
    parser.add_argument("template", help="path to Python 3 template file")
    parser.add_argument("output", help="path to output file")

    args = parser.parse_args()

    if args.template.endswith(".py"):
        render_fn = pydantic_doc.render_python
    else:
        print("WARNING: Unrecognized template format:", args.template)
        render_fn = None

    if render_fn:
        render_fn(args.output, args.template)
