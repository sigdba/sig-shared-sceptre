#!/usr/bin/env bash

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

cd $SCRIPT_DIR

echo "--- DIFF ---"
diff -ur baseline current
status=$?
echo "------------"

exit $status
