#!/usr/bin/env bash

shopt -s nullglob

die () {
    echo "ERROR: $*"
    exit 1
}

if [ "$#" -ne 1 ]; then
   echo "usage: $0 <release>"
   exit 1
fi
tag="$1"

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

pkg_dir=${BASE}/packages
mkdir -p $pkg_dir || die "unable to create $pkg_dir"

for tdir in ${BASE}/templates/*; do
    if [ -d "$tdir" ]; then
        tname=$(basename $tdir)
        zipfile=${pkg_dir}/${tname}-${tag}.zip
        cd $tdir
        zip -r ${zipfile} . --exclude __pycache__/\* 1>&2 || die "zip failed"
        echo $zipfile
    fi
done
