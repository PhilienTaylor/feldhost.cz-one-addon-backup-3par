#!/usr/bin/env bash

SCRIPT_PATH=$(dirname $0)

. ${SCRIPT_PATH}/helper_scripts.sh

LUN=$1
WWN=$2

DISCOVER_CMD=$(cat <<EOF
    set -e
    $(discover_lun "$LUN" "$WWN")
EOF
)

exec_and_log "$DISCOVER_CMD" \
    "Error discovering LUN $LUN:$WWN"

exit 0