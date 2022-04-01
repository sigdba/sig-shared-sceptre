#!/usr/bin/env bash

shopt -s nullglob

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
TEMPLATES=${BASE}/templates
GENDOC="python3 $SCRIPT_DIR/gendoc.py"

for model_path in $(grep -l 'class UserDataModel(BaseModel' $BASE/templates/*/*.py); do
    template_path=$(grep -l 'def sceptre_handler(' $(dirname $model_path)/*.py)
    md_file="$(dirname $template_path)/readme.md"
    echo "Documenting ${template_path/$TEMPLATES} -> ${md_file/$TEMPLATES}"
    $GENDOC "$template_path" "$md_file" || die "Error generating documentation"
done

cat ${BASE}/build/readme-header.md >${BASE}/readme.md
for t in ${BASE}/templates/*; do
    tdoc=${t}/readme.md
    tname=$(basename ${t})
    if [ -f ${tdoc} ]; then
        echo "- [${tname}](${tdoc##$BASE/})" >>${BASE}/readme.md
    else
        echo "WARNING: ${tdoc} not found"
        echo "- $tname" >>${BASE}/readme.md
    fi
    for d in ${t}/doc/*.md; do
        echo "  - [$(basename $d)](${d##$BASE/})" >>${BASE}/readme.md
    done

    examples=${t}/examples
    if [ -d ${examples} ]; then
        echo "  - [Examples](${examples##$BASE/})" >>${BASE}/readme.md
    fi
done

cat ${BASE}/build/readme-footer.md >>${BASE}/readme.md
