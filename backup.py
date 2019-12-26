#!/usr/bin/env python

import argparse
import datetime
import time

import config
import pyone
import functions

# ----------------------------
# Define parser
# ----------------------------
parser = argparse.ArgumentParser(description='OpenNebula Backup Tool')

parser.add_argument('-i', '--image', help='Image id or comma separated list of image ids to backup. Omit for backup all images', type=functions.list_of_int_arg)
parser.add_argument('-S', '--startImage', help='Image id to start backup from. Backups all following images including defined one', type=int)
parser.add_argument('-a', '--datastore', help='Datastore id or comma separated list of datastore ids to backup from. Omit to backup from all datastores to backup', type=functions.list_of_int_arg)
parser.add_argument('-l', '--label', help='Label or comma separated list of labels of tagged images', type=functions.list_arg)
parser.add_argument('-e', '--exclude', help='Skip (exclude) by label or comma separated list of labels of tagged images', type=functions.list_arg)
parser.add_argument('-P', '--pruneOnly', help='Don\'t backup anything, just prune old backups', action='store_true')
parser.add_argument('-D', '--deployments', help='Not implemented yet! Backup also deployments files from system datastores', action='store_true')
parser.add_argument('-d', '--dryRun', help='Not implemented yet! Dry run - not execute any commands, all cmds will be just printed', action='store_true')
parser.add_argument('-v', '--verbose', help='Verbose mode', action='store_true')

# -------------------------------------
# Parse args and proceed with execution
# -------------------------------------
args = parser.parse_args()

# -----------------------
# Connect to OpenNebula
# -----------------------
one = pyone.OneServer(config.ONE['address'], session='%s:%s' % (config.ONE['username'], config.ONE['password']))

datastores = functions.prepare_datastores(one, args)
all_images = functions.prepare_images(one, args)
images = functions.filter_images(all_images, datastores, args)

# connect and login to 3PAR
from drivers import _3par
_3par.login()

# starting backup
if not args.pruneOnly:
    functions.send_email('Backup started! Images count: %d' % len(images))

for image_key in images:
    image = images[image_key]
    datastore = datastores[image.DATASTORE_ID]

    # only datastores with 3PAR transfer manager
    if datastore.TM_MAD != '3par':
        continue

    # prune only?
    if args.pruneOnly:
        try:
            _3par.prune(image, args.verbose)
        except Exception as ex:
            print ex
            functions.send_email('Error prune image %d:%s: "%s"' % (image.ID, image.NAME, ex))
        continue

    # mark start of backup in verbose output
    if args.verbose:
        print '#============================================================'

    # set info abut backup start to image template
    one.image.update(image.ID, 'BACKUP_IN_PROGRESS=YES BACKUP_FINISHED_UNIX=--- BACKUP_FINISHED_HUMAN=--- BACKUP_STARTED_UNIX=%d BACKUP_STARTED_HUMAN="%s"' % (int(time.time()), datetime.datetime.now().ctime()), 1)

    # lock image
    if config.LOCK_RESOURCES:
        if args.verbose:
            print 'Locking image %d:%s' % (image.ID, image.NAME)
        one.image.lock(image.ID, 4)

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
            functions.send_email('Can not found VM Disk ID for image %d:%s attached to VM %d:%s' % (image.ID, image.NAME, vmId, vm.NAME))
            continue

        if args.verbose:
            print 'Backup persistent image %d:%s attached to VM %d:%s as disk %d' % (image.ID, image.NAME, vmId, vm.NAME, vmDiskId)

        # lock VM
        if config.LOCK_RESOURCES:
            if args.verbose:
                print 'Locking VM %d:%s' % (vmId, vm.NAME)
            one.vm.lock(vmId, 4)

        try:
            _3par.backup_live(one, image, vm, vmDiskId, args.verbose)
        except Exception as ex:
            print ex
            functions.send_email('Error backup image %d:%s: "%s"' % (image.ID, image.NAME, ex))
            continue

        # unlock VM
        if config.LOCK_RESOURCES:
            if args.verbose:
                print 'Unlocking VM %d:%s' % (vmId, vm.NAME)
            one.vm.unlock(vmId)

    # persistent not attached
    elif image.PERSISTENT == 1:
        if args.verbose:
            print 'Backup persistent not attached image %d:%s' % (image.ID, image.NAME)

        try:
            _3par.backup(image, args.verbose)
        except Exception as ex:
            print ex
            functions.send_email('Error backup image %d:%s: "%s"' % (image.ID, image.NAME, ex))
            continue

    # non-persistent
    elif image.PERSISTENT == 0:
        if args.verbose:
            print 'Backup non-persistent image %d:%s' % (image.ID, image.NAME)

        try:
            _3par.backup(image, args.verbose)
        except Exception as ex:
            print ex
            functions.send_email('Error backup image %d:%s: "%s"' % (image.ID, image.NAME, ex))
            continue

    # unlock image
    if config.LOCK_RESOURCES:
        if args.verbose:
            print 'Unlocking image %d:%s' % (image.ID, image.NAME)
        one.image.unlock(image.ID)

    # set info abut backup start to image template
    one.image.update(image.ID, 'BACKUP_IN_PROGRESS=NO BACKUP_FINISHED_UNIX=%d BACKUP_FINISHED_HUMAN="%s"' % (int(time.time()), datetime.datetime.now().ctime()), 1)

    # mark end of backup in verbose output
    if args.verbose:
        print '#============================================================'

# show borgbackup info
if args.verbose:
    try:
        print functions.borgbackup_info()
    except Exception as ex:
        print ex

# disconnect form 3PAR
_3par.logout()
