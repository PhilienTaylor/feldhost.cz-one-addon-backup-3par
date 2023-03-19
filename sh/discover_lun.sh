#!/usr/bin/env bash

SCRIPT_PATH=$(dirname $0)

. ${SCRIPT_PATH}/helper_scripts.sh

LUN=$1
WWN=$2

DISCOVER_CMD=$(cat <<EOF
    function discover {
        $(discover_lun "$LUN" "$WWN")
    }

    function remove {
        $(remove_lun "$WWN")
    }

    discover
    if [[ \$? -ne 0 ]]; then
        remove && discover
        if [[ \$? -ne 0 ]]; then
            exit 1
        fi
    fi
EOF
)

exec_and_log "$DISCOVER_CMD" \
    "Error discovering LUN $LUN:$WWN"

exit 0