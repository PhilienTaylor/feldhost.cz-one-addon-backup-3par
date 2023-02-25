#@IgnoreInspection BashAddShebang
# -------------------------------------------------------------------------- #
# Copyright 2019, FeldHost™ (feldhost.net)                                   #
#                                                                            #
# Portions copyright 2014-2016, Laurent Grawet <dev@grawet.be>               #
#                                                                            #
# Licensed under the Apache License, Version 2.0 (the "License"); you may    #
# not use this file except in compliance with the License. You may obtain    #
# a copy of the License at                                                   #
#                                                                            #
# http://www.apache.org/licenses/LICENSE-2.0                                 #
#                                                                            #
# Unless required by applicable law or agreed to in writing, software        #
# distributed under the License is distributed on an "AS IS" BASIS,          #
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.   #
# See the License for the specific language governing permissions and        #
# limitations under the License.                                             #
# -------------------------------------------------------------------------- #

export LANG=C

SUDO=sudo
READLINK=readlink
BLOCKDEV=blockdev
DMSETUP=dmsetup
MULTIPATH=multipath
MULTIPATHD=multipathd
TEE=tee
BASENAME=basename

# Log function that knows how to deal with severities and adds the
# script name
function log_function
{
    echo "$1: $SCRIPT_NAME: $2" 1>&2
}

# Logs an info message
function log_info
{
    log_function "INFO" "$1"
}

# Logs an error message
function log_error
{
    log_function "ERROR" "$1"
}

# Logs a debug message
function log_debug
{
    log_function "DEBUG" "$1"
}

# This function is used to pass error message to the mad
function error_message
{
    (
        echo "ERROR MESSAGE --8<------"
        echo "$1"
        echo "ERROR MESSAGE ------>8--"
    ) 1>&2
}

# Executes a command, if it fails returns error message and exits
# If a second parameter is present it is used as the error message when
# the command fails
function exec_and_log
{
    EXEC_LOG_ERR=`bash -s 2>&1 1>/dev/null <<EOF
export LANG=C
export LC_ALL=C
$1
EOF`
    EXEC_LOG_RC=$?

    if [ $EXEC_LOG_RC -ne 0 ]; then
        log_error "Command \"$1\" failed: $EXEC_LOG_ERR"

        if [ -n "$2" ]; then
            error_message "$2"
        else
            error_message "Error executing $1: $EXEC_LOG_ERR"
        fi
        exit $EXEC_LOG_RC
    fi
}

function multipath_flush {
    local MAP_NAME
    MAP_NAME="$1"
    echo "$SUDO $MULTIPATH -f $MAP_NAME"
}

function multipath_rescan {
    echo "$SUDO $MULTIPATH"
    echo "sleep 4"
}

function rescan_scsi_bus {
  local LUN
  local FORCE
  LUN="$1"
  [ "$2" == "force" ] && FORCE=" --forcerescan"
  echo "HOSTS=\$(cat /proc/scsi/scsi | awk -v RS=\"Type:\" '\$0 ~ \"Vendor: 3PARdata\" {print \$0}' |grep -Po \"scsi[0-9]+\"|grep -Eo \"[0-9]+\" |sort|uniq|paste -sd \",\" -)"
  echo "$SUDO /usr/bin/rescan-scsi-bus.sh --hosts=\$HOSTS --luns=$LUN --nooptscan$FORCE"
}

function discover_lun {
    local LUN
    local WWN
    LUN="$1"
    WWN="$2"
    cat <<EOF
        $(rescan_scsi_bus "$LUN")

        DEV="/dev/mapper/3$WWN"

        # Wait a bit for new mapping
        COUNTER=1
        while [ ! -e \$DEV ] && [ \$COUNTER -le 10 ]; do
            sleep 1
            COUNTER=\$((\$COUNTER + 1))
        done

        # Exit with error if mapping does not exist
        if [ ! -e \$DEV ]; then
            echo 'Mapping does not exists'
            exit 1
        fi

        DM_HOLDER=\$($SUDO $DMSETUP ls -o blkdevname | grep -Po "(?<=3$WWN\s\()[^)]+")
        DM_SLAVE=\$(ls /sys/block/\${DM_HOLDER}/slaves)
        # Wait a bit for mapping's paths
        COUNTER=1
        while [ ! "\${DM_SLAVE}" ] && [ \$COUNTER -le 10 ]; do
            sleep 1
            COUNTER=\$((\$COUNTER + 1))
        done
        # Exit with error if mapping has no path
        if [ ! "\${DM_SLAVE}" ]; then
            echo 'Mapping has no path'
            exit 1
        fi
EOF
}

function remove_lun {
    local WWN
    WWN="$1"
    cat <<EOF
      DEV="/dev/mapper/3$WWN"
      DM_HOLDER=\$($SUDO $DMSETUP ls -o blkdevname | grep -Po "(?<=3$WWN\s\()[^)]+")
      DM_SLAVE=\$(ls /sys/block/\${DM_HOLDER}/slaves)

      unset device
      for device in \${DM_SLAVE}
      do
          if [ -e /dev/\${device} ]; then
              $SUDO $BLOCKDEV --flushbufs /dev/\${device}
              echo 1 | $SUDO $TEE /sys/block/\${device}/device/delete
          fi
      done

      # wait for auto remove multipath
      EXISTS=1
      COUNTER=1
      while [ "\${DM_SLAVE}" ] && [ \$EXISTS -gt 0 ] && [ \$COUNTER -le 10 ]; do
          sleep 1
          EXISTS=\$($SUDO $MULTIPATH -ll 3$WWN | head -c1 | wc -c)
          COUNTER=\$((\$COUNTER + 1))
      done

      if [[ \$EXISTS -gt 0 ]]; then
          # Wait for releasing device
          OPEN_COUNT=1
          while [ \$OPEN_COUNT -gt 0 ]; do
              sleep 1
              OPEN_COUNT=\$($SUDO $DMSETUP info 3$WWN | grep -P "Open\scount:" | grep -oP "[0-9]+")
          done

          $(multipath_flush "3$WWN")
      fi
EOF
}