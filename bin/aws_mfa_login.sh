#!/usr/bin/env bash

set -eo pipefail

unset AWS_ACCESS_KEY_ID
unset AWS_SECRET_ACCESS_KEY
unset AWS_SESSION_TOKEN

MFA_DEVICE="${1}" # MFA device serial number
MFA_CODE="${2}"   # MFA token code

[ -z "${MFA_CODE}" ] || [ -z "${MFA_DEVICE}" ] && \
  { echo "No MFA code or device provided" && \
    echo "Usage: source aws_mfa_login.sh MFA_DEVICE MFA_CODE" \
  ; } || \
  { CREDS=`aws sts get-session-token --serial-number ${MFA_DEVICE} --token-code ${MFA_CODE}` && \
    export AWS_ACCESS_KEY_ID="`echo -n $CREDS | jq -r '.Credentials.AccessKeyId'`" \
           AWS_SECRET_ACCESS_KEY="`echo -n $CREDS | jq -r '.Credentials.SecretAccessKey'`" \
           AWS_SESSION_TOKEN="`echo -n $CREDS | jq -r '.Credentials.SessionToken'`" \
  ; }
