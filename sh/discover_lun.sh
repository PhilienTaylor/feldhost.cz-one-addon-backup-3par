#!/usr/bin/env bash

SCRIPT_PATH=$(dirname $0)

. ${SCRIPT_PATH}/helper_scripts.sh

LUN=$1
WWN=$2

DISCOVER_CMD=$(cat <<EOF
    discover_lun "$LUN" "$WWN"
    if [[ $? -ne 0 ]] then
        remove_lun "$WWN" && discover_lun "$LUN" "$WWN"
        if [[ $? -ne 0 ]] then
            exit 1
        fi
    fi
EOF
)

exec_and_log "$DISCOVER_CMD" \
    "Error discovering LUN $LUN:$WWN"

exit 0