#!/usr/bin/env bash

set -e
set -o pipefail

die () {
    >&2 echo "ERROR: $*"
    exit 1
}

unset AWS_ACCESS_KEY_ID
unset AWS_SECRET_ACCESS_KEY
unset AWS_SESSION_TOKEN

user=$(aws sts get-caller-identity --output=text |cut -f 2 |cut -d '/' -f 2)

>&2 echo "      User: $user"

mfa_id=$(aws iam list-mfa-devices --user-name "$user" --output=text |cut -f 3)

>&2 printf "MFA Device: $mfa_id\n\n"

read -p "Enter MFA Code: " mfa_code

res=$(aws sts get-session-token --serial-number "$mfa_id" --token-code "$mfa_code" --output=text)

key_id=$(echo "$res" |cut -f 2)
secret=$(echo "$res" |cut -f 4)
session=$(echo "$res" |cut -f 5)

[ -z "$key_id" ] && die "no access key id"
[ -z "$secret" ] && die "no secret access key"
[ -z "$session" ] && die "no session token"

echo "AWS_ACCESS_KEY_ID=$key_id; export AWS_ACCESS_KEY_ID"
echo "AWS_SECRET_ACCESS_KEY=$secret; export AWS_SECRET_ACCESS_KEY"
echo "AWS_SESSION_TOKEN=$session; export AWS_SESSION_TOKEN"
