#!/usr/bin/env python

import argparse
import pprint

import config
import pyone
import functions

# ----------------------------
# Define parser
# ----------------------------
parser = argparse.ArgumentParser(description='OpenNebula Backup Tool')

parser.add_argument('-i', '--image', help='Image id or comma separated list of image ids to backup. Omit for backup all images', type=functions.list_of_int_arg)
parser.add_argument('-S', '--startImage', help='Image id to start backup from. Backups all following images including defined one', type=int)
parser.add_argument('-a', '--dataStore', help='Datastore id or comma separated list of datastore ids to backup from. Omit to backup from all datastores to backup', type=functions.list_of_int_arg)
parser.add_argument('-l', '--label', help='Label or comma separated list of labels of tagged images or datastores', type=functions.list_arg)
parser.add_argument('-e', '--exclude', help='Skip (exclude) by label or comma separated list of labels of tagged images or datastores', type=functions.list_arg)
parser.add_argument('-D', '--deployments', help='Backup also deployments files from system datastores', action='store_true')
parser.add_argument('-d', '--dryRun', help='Dry run - not execute any commands, all cmds will be just printed', action='store_true')
parser.add_argument('-v', '--verbose', help='Verbose mode', action='store_true')

# -------------------------------------
# Parse args and proceed with execution
# -------------------------------------
args = parser.parse_args()

# -----------------------
# Connect to OpenNebula
# -----------------------
one = pyone.OneServer(config.ONE['address'], session='%s:%s' % (config.ONE['username'], config.ONE['password']))

imagePool = one.imagepool.info(-2, -1, -1)

# connect and login to 3PAR
from drivers import _3par
_3par.login()

for image in imagePool.IMAGE:
    dataStore = one.datastore.info(image.DATASTORE_ID)

    # skip other datastores
    if dataStore.TM_MAD != '3par':
        continue

    # persistent and attached to VM
    if image.PERSISTENT == 1 and image.RUNNING_VMS > 0:
        vmId = image.VMS.ID[0]
        vm = one.vm.info(vmId)
        vmDiskId = None

        if isinstance(vm.TEMPLATE.get('DISK'), list):
            for vmDisk in vm.TEMPLATE.get('DISK'):
                if int(vmDisk.get('IMAGE_ID')) == image.ID:
                    vmDiskId = int(vmDisk.get('DISK_ID'))
                    break
        else:
            vmDiskId = int(vm.TEMPLATE.get('DISK').get('DISK_ID'))

        if vmDiskId is None:
            # error
            print 'Can not found VM Disk ID for image %d:%s attached to VM %d:%s' % (image.ID, image.NAME, vmId, vm.NAME)
            continue

        if args.verbose:
            print 'Backup persistent image %d:%s attached to VM %d:%s as disk %d' % (image.ID, image.NAME, vmId, vm.NAME, vmDiskId)

        try:
            _3par.backup_live(one, image, dataStore, vm, vmDiskId, args.verbose)
        except Exception as ex:
            print ex
            continue

        break
    # persistent not attached
    elif image.PERSISTENT == 1:
        if args.verbose:
            print 'Backup persistent not attached image %d:%s' % (image.ID, image.NAME)

    # non-persistent
    elif image.PERSISTENT == 0:
        if args.verbose:
            print 'Backup non-persistent image %d:%s' % (image.ID, image.NAME)


# disconnect form 3PAR
_3par.logout()
