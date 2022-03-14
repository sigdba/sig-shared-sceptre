#!/usr/bin/env bash

echo "--- DIFF ---"
diff -ur baseline current
status=$?
echo "------------"

exit $status
