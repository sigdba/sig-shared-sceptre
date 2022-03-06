#!/usr/bin/env bash

die () {
    echo "ERROR: $*"
    exit 1
}

# Determine SCRIPT_DIR
[ -z "$SHELL" ] && SHELL=/bin/bash
case $(basename $SHELL) in
	zsh)
		SCRIPT_DIR=$(dirname $0:A)
		;;

	*)
		SCRIPT_DIR=$(cd $(dirname $0); pwd)
		;;
esac

BASE="$(cd "$SCRIPT_DIR/.."; pwd -P)"
GENDOC="python3 $SCRIPT_DIR/gendoc.py"

for template_path in $(grep -l 'class UserDataModel(BaseModel' $BASE/templates/*/*.py); do
    md_file="$(dirname $template_path)/readme.md"
    echo "Documenting $template_path -> $md_file"
    $GENDOC "$template_path" "$md_file" || die "Error generating documentation"
done
