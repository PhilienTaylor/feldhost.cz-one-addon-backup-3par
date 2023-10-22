#!/usr/bin/env python3

import argparse
import os
import subprocess
import sys
import time
try:
    from StringIO import StringIO ## for Python 2
except ImportError:
    from io import StringIO ## for Python 3
from drivers import _3par

import config
import pyone

base_path = os.path.abspath(os.path.dirname(sys.argv[0]))

# ----------------------------
# Define parser
# ----------------------------
parser = argparse.ArgumentParser(description='OpenNebula Restore from backup Tool')
subparsers = parser.add_subparsers(title='List of available tasks', description='You can view help for each task by passing task name and -h option', dest='task')

# Common Parser
commonParser = argparse.ArgumentParser(add_help=False)
commonParser.add_argument('-i', '--image', help='Image id to restore', type=int, required=True)
commonParser.add_argument('-d', '--dryRun', help='Not implemented yet! Dry run - not execute any commands, all cmds will be just printed', action='store_true')
commonParser.add_argument('-v', '--verbose', help='Verbose mode', action='store_true')

# List backups task parser
listBackupsParser = subparsers.add_parser('list', parents=[commonParser], help='List available backup for given image')

# Restore specific backup task parser
restoreBackupParser = subparsers.add_parser('restore', parents=[commonParser], help='Restore specific backup for given image')
restoreBackupParser.add_argument('-sid', '--snapshotId', help='Define specific backup by its snapshot ID. Use list task to get available backups', required=True)
restoreBackupParser.add_argument('-ti', '--targetImage', help='Target image ID in OpenNebula datastore', type=int)
restoreBackupParser.add_argument('-tds', '--targetDatastore', help='Target OpenNebula datastore where new image to be create', type=int)
restoreBackupParser.add_argument('-bs', '--bs', help='Define Block Size for DD command. Default 1M', default='1M')
restoreBackupParser.add_argument('-sc', '--skipCheck', help='Skip check if disk is used', action='store_true')

def vv_name_wwn(source):
    ex = source.split(':')

    return ex[0], ex[1]

def split_datetime(datetime):
    ex = datetime.split('T')

    return ex[0], ex[1]

def allocateImage(one, name, image, datetime, datastore):
    imageTypes = {0: 'OS', 1: 'CDROM', 2: 'DATABLOCK'}
    imagePersistent = {0: 'NO', 1: 'YES'}

    # allocate new image in datastore 101
    template = 'NAME="%s" TYPE=%s SIZE=%d PERSISTENT=%s DEV_PREFIX=sd DRIVER=raw RESTORE_FROM_DATETIME=%s LABELS=nobackup' % (
    name, imageTypes[image.TYPE], image.SIZE, imagePersistent[image.PERSISTENT], datetime)

    try:
        # allocate new image in the cloud
        id = one.image.allocate(template, datastore)

        # get new image info
        source = None
        while not source:
            image = one.image.info(id)
            source = image.SOURCE
            time.sleep(1)

        return image
    except Exception as ex:
        print(ex)
        exit(1)


def _list(one, args):
    # get opennebula image
    image = one.image.info(args.image)

    try:
        result = subprocess.check_output('KOPIA_CHECK_FOR_UPDATES=false KOPIA_PASSWORD="none" kopia repository connect filesystem --readonly --path=%s/%s && kopia snapshot list %s/%s/image' % (config.BACKUP_PATH, image.ID, config.BACKUP_PATH, image.ID), shell=True).decode('utf-8')
        print(result)

    except subprocess.CalledProcessError as ex:
        raise Exception('Can not list kopia backups', ex)


def _restore(one, args):
    # validate input
    if not args.targetImage and not args.targetDatastore:
        raise Exception('Define target image ID or datastore ID please!')

    # get info about src image
    srcImage = one.image.info(args.image)

    # validate if given datetime exists
    subprocess.check_call('KOPIA_PASSWORD="none" kopia snapshot list %s/%s/image | grep %s' % (config.BACKUP_PATH, srcImage.ID, args.snapshotId), shell=True)

    if args.targetImage:
        # get info about dest image
        destImage = one.image.info(args.targetImage)
        # get datastore info
        datastore = one.datastore.info(destImage.DATASTORE_ID)
        # check state
        if not args.skipCheck and destImage.STATE != 1:
            raise Exception('Target image is not in READY state!')
    elif args.targetDatastore:
        datetime = subprocess.check_output(
            'KOPIA_PASSWORD="none" kopia snapshot list %s/%s/image | grep %s | grep -Po "[0-9]{4}-[0-9]{2}-[0-9]{2}\s[0-9]{2}:[0-9]{2}:[0-9]{2}"' % (
            config.BACKUP_PATH, srcImage.ID, args.snapshotId), shell=True).decode('utf-8')
        datetime = datetime.replace(' ', 'T')
        date, dtime = split_datetime(datetime)
        restoreName = '%s-restore-%s' % (srcImage.NAME, date)
        destImage = allocateImage(one, restoreName, srcImage, datetime, args.targetDatastore)
        # get datastore info
        datastore = one.datastore.info(args.targetDatastore)

    # get vv name and wwn
    destName, destWwn = vv_name_wwn(destImage.SOURCE)

    # connect and login to 3PAR
    _3par.login(datastore.TEMPLATE.get('API_ENDPOINT'), datastore.TEMPLATE.get('IP'))

    # export volume to backup server
    print('Exporting volume %s to backup server...' % destName)
    lun_no = _3par.export_vv(destName, config.EXPORT_HOST)

    # discover volume
    print('Volume is exported as LUN %d with WWN %s on %s. Discovering LUN...' % (lun_no, destWwn, config.EXPORT_HOST))
    subprocess.check_call('%s/sh/discover_lun.sh %d %s' % (base_path, lun_no, destWwn), shell=True)

    # restore voleme from backup
    print('Restore volume from backup to exported lun')
    # calculate size
    size = destImage.SIZE * 1024 * 1024
    subprocess.check_output('set -o pipefail && KOPIA_PASSWORD="none" kopia show %s | pv -pterab -s %d | dd of=/dev/mapper/3%s bs=%s iflag=fullblock oflag=direct' % (args.snapshotId, size, destWwn, args.bs),
                                  shell=True)

    # flush volume
    print('Flushing LUN...')
    try:
        subprocess.check_call('%s/sh/flush_lun.sh %s' % (base_path, destWwn), shell=True)
    except subprocess.CalledProcessError as ex:
        raise Exception('Can not flush LUN', ex)

    # unexport volume
    print('Unexporting volume %s from backup server...' % destName)
    _3par.unexport_vv(destName, config.EXPORT_HOST)

    _3par.logout()


# -------------------------------------
# Parse args and proceed with execution
# -------------------------------------
args = parser.parse_args()

# -----------------------
# Connect to OpenNebula
# -----------------------
one = pyone.OneServer(config.ONE['address'], session='%s:%s' % (config.ONE['username'], config.ONE['password']))

try:
    globals()[('_%s' % args.task)](one, args)
except Exception as ex:
    # something unexpected happened
    print(ex)
    exit(1)
