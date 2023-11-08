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
export PIPENV_VERBOSITY=-1
GENDOC="pipenv run python3 $SCRIPT_DIR/gendoc/gendoc.py"

for template_dir in $TEMPLATES/*; do
    [ -d "$template_dir" ] || continue
    if [ ! -f "${template_dir}/manifest.yaml" ]; then
      echo "WARNING: Skipping $template_dir"
      continue
    fi
    entrypoint=$(awk '$1 ~ /^entrypoint:/ {print $2}' "$template_dir/manifest.yaml")
    template_path="$template_dir/$entrypoint"
    md_file="${template_dir}/readme.md"
    tmp_md="${md_file}.tmp"
    echo "Documenting ${template_path/$TEMPLATES} -> ${md_file/$TEMPLATES}"
    $GENDOC "$template_path" "$tmp_md" || die "Error generating documentation"
    if [ -f "$tmp_md" ]; then
        rm -f "$md_file"
        [ -f "$template_dir/.readme-head.md" ] && cat "$template_dir/.readme-head.md" >$md_file
        cat "$tmp_md" >>$md_file
        [ -f "$template_dir/.readme-foot.md" ] && cat "$template_dir/.readme-foot.md" >$md_file
        rm -f "$tmp_md"
    fi
done

cat ${BASE}/build/readme-header.md >${BASE}/readme.md
for t in ${BASE}/templates/*; do
    if [ ! -f "${t}/manifest.yaml" ]; then
      echo "WARNING: Skipping $t"
      continue
    fi
    tdoc=${t}/readme.md
    tname=$(basename ${t})
    if [ -f ${tdoc} ]; then
        blurb=""
        [ -f "${t}/.readme-head.md" ] && blurb=$(grep '^\w' "${t}/.readme-head.md" |tr '\n' ' ' |grep -o '^[^.]*\.')
        [ -n "$blurb" ] && blurb=" - $blurb"
        echo "- [${tname}](${tdoc##$BASE/})${blurb}" >>${BASE}/readme.md
    else
        echo "WARNING: ${tdoc} not found"
        echo "- $tname" >>${BASE}/readme.md
    fi
    for d in ${t}/doc/*.md ${t}/doc/*.org; do
        echo "  - [$(basename $d)](${d##$BASE/})" >>${BASE}/readme.md
    done

    examples=${t}/examples
    if [ -d ${examples} ]; then
        echo "  - [Examples](${examples##$BASE/})" >>${BASE}/readme.md
    fi
done

cat ${BASE}/build/readme-footer.md >>${BASE}/readme.md
