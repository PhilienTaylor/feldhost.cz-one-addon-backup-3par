#!/usr/bin/env bash

SCRIPT_PATH=$(dirname $0)

. ${SCRIPT_PATH}/helper_scripts.sh

WWN=$1

FLUSH_CMD=$(cat <<EOF
    function remove {
        $(remove_lun "$WWN")
    }

    remove
    if [[ \$? -ne 0 ]]; then
        exit 1
    fi
EOF
)

exec_and_log "$FLUSH_CMD" \
    "Error flushing LUN $WWN"

exit 0