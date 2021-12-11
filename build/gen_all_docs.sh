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

mkdir -p "$BASE/doc"

for template_path in $BASE/*/*/main.py; do
    title="${template_path#$BASE}"
    title="${title#/}"
    md_file="$BASE/doc/$(echo "${title%/main.py}" |tr '/' '_').md"
    echo "Documenting $template_path -> $md_file"
    $GENDOC "$template_path" "$md_file" || die "Error generating documentation"
done

for template_path in $(grep -l 'class UserDataModel(BaseModel' $BASE/*.py); do
    md_file="$BASE/doc/$(basename "$template_path" .py).md"
    echo "Documenting $template_path -> $md_file"
    $GENDOC "$template_path" "$md_file" || die "Error generating documentation"
done
