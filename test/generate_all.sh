#!/usr/bin/env bash
set -euo pipefail

# Suppress messages about virtual environments from pipenv
export PIPENV_VERBOSITY=-1

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

die () {
  echo "ERROR: $*"
  exit 1
}

# Make SCRIPT_DIR absolute
SCRIPT_DIR="$(cd "$SCRIPT_DIR"; pwd -P)"
cd $SCRIPT_DIR

SCEPTRE_DIR="$SCRIPT_DIR"
OUT_DIR="$SCRIPT_DIR/current"

gen_stack () {
    D="$1"
    T="$2"
    OUT="$D/$T"

    echo ${OUT}
    cd "$SCEPTRE_DIR"
    mkdir -p "$(dirname $OUT)"
    pipenv run sceptre --output=yaml generate ${T} >${OUT}
}
export -f gen_stack

list_stacks () {
    TEMPLATE="template:.*\.py" # Match all
    cd "$SCEPTRE_DIR/config"
    grep -lr "$TEMPLATE" *
    cd "$SCEPTRE_DIR"
}

echo "Generating stacks into $OUT_DIR"

cd $SCEPTRE_DIR
list_stacks | parallel -j 300% --halt now,fail=1 gen_stack $OUT_DIR {}
