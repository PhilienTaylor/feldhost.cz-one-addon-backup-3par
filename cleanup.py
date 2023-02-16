#!/usr/bin/env python3

import os
import subprocess
import sys
import re

from drivers import _3par
import pyone

import config

base_path = os.path.abspath(os.path.dirname(sys.argv[0]))

# reset the multipathd wwids file to include only the current devices
try:
    subprocess.check_call('multipath -W', shell=True)
    pass
except subprocess.CalledProcessError as ex:
    raise Exception('Failed to reset wwids', ex)

# read wwids file
wwns = []
with open('/etc/multipath/wwids') as wwids:
    for line in wwids:
        match = re.search('^/3([^/]+)/$', line)
        if match:
            wwn = match.group(1)
            wwns.append(wwn)

# Connect to OpenNebula and 3PAR
one = pyone.OneServer(config.ONE['address'], session='%s:%s' % (config.ONE['username'], config.ONE['password']))
_3par.login()

volumes = _3par.get_list_of_exported_volumes()

# iterate over wwns
for wwn in wwns:
    # flush volume
    print('Flushing LUN...')
    try:
        subprocess.check_call('%s/sh/flush_lun.sh %s' % (base_path, wwn), shell=True)
    except subprocess.CalledProcessError as ex:
        raise Exception('Can not flush LUN', ex)

    if wwn in volumes:
        name = volumes.get(wwn).get('name')

        # unexport volume
        print('Unexporting volume %s from backup server...' % name)
        _3par.unexport_vv(name, config.EXPORT_HOST)

        match = re.match('feldcloud\.one\.([0-9]+)\.vv\.([0-9]+)', name)
        if match:
            imageId = int(match[1])
            snapId = int(match[2])
            image = one.image.info(imageId)
            vmId = image.VMS.ID[0]
            vm = one.vm.info(vmId)

            disks = vm.TEMPLATE.get('DISK')
            if isinstance(disks, dict):
                disks = [disks]

            diskId = None
            for disk in disks:
                if int(disk.get('IMAGE_ID')) == imageId:
                    diskId = int(disk.get('DISK_ID'))
                    break

            if diskId is not None:
                print('Deleting disk snapshot: vmID:%d diskId:%d snapId:%d' % (vmId, diskId, snapId))
                one.vm.disksnapshotdelete(vmId, diskId, snapId)
