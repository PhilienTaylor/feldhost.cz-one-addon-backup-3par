#!/usr/bin/env python

import argparse
import os
import subprocess
import sys
import time
from StringIO import StringIO

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
listBackupsParser.add_argument('-e', '--extended', help='Show extended info for each backup', action='store_true')

# Info backup task parser
infoBackupParser = subparsers.add_parser('info', parents=[commonParser], help='Get info about specific backup for given image')
infoBackupParser.add_argument('-dt', '--datetime', help='Define specific backup by its datetime. Use list task to get available backups', required=True)

# Restore specific backup task parser
restoreBackupParser = subparsers.add_parser('restore', parents=[commonParser], help='Restore specific backup for given image')
restoreBackupParser.add_argument('-dt', '--datetime', help='Define specific backup by its datetime. Use list task to get available backups', required=True)
restoreBackupParser.add_argument('-ti', '--targetImage', help='Target image ID in OpenNebula datastore', type=int)
restoreBackupParser.add_argument('-tds', '--targetDatastore', help='Target OpenNebula datastore where new image to be create', type=int)
restoreBackupParser.add_argument('-bs', '--bs', help='Define Block Size for DD command. Default 10M', default='10M')

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
    template = 'NAME=%s TYPE=%s SIZE=%d PERSISTENT=%s DEV_PREFIX=sd DRIVER=raw RESTORE_FROM_DATETIME=%s LABELS=nobackup' % (
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
        print ex
        exit(1)


def _list(one, args):
    # get opennebula image
    image = one.image.info(args.image)

    # get source name and wwn
    name, wwn = vv_name_wwn(image.SOURCE)

    try:
        result = subprocess.check_output('borg list %s/%s | grep -Po "[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"' % (config.BACKUP_PATH, image.ID), shell=True)

        if args.extended:
            s = StringIO(result)
            for line in s:
                subprocess.check_call('borg info %s/%s::%s' % (config.BACKUP_PATH, image.ID, line), shell=True)
        else:
            print result

    except subprocess.CalledProcessError as ex:
        raise Exception('Can not list borg backups', ex)


def _info(one, args):
    # get opennebula image
    image = one.image.info(args.image)

    # get source name and wwn
    name, wwn = vv_name_wwn(image.SOURCE)

    subprocess.check_call('borg info %s/%s::%s' % (config.BACKUP_PATH, image.ID, args.datetime), shell=True)


def _restore(one, args):
    # validate input
    if not args.targetImage and not args.targetDatastore:
        raise Exception('Define target image ID or datastore ID please!')

    # get info about src image
    srcImage = one.image.info(args.image)
    srcName, srcWwn = vv_name_wwn(srcImage.SOURCE)

    # validate if given datetime exists
    subprocess.check_call('borg info %s/%s::%s' % (config.BACKUP_PATH, srcImage.ID, args.datetime), shell=True)

    if args.targetImage:
        # get info about dest image
        destImage = one.image.info(args.targetImage)
        # check state
        if destImage.STATE != 1:
            raise Exception('Target image is not in READY state!')
    elif args.targetDatastore:
        date, time = split_datetime(args.datetime)
        restoreName = '%s-restore-%s' % (srcImage.NAME, date)
        destImage = allocateImage(one, restoreName, srcImage, args.datetime, args.targetDatastore)

    # get vv name and wwn
    destName, destWwn = vv_name_wwn(destImage.SOURCE)

    # connect and login to 3PAR
    from drivers import _3par
    _3par.login()

    # export volume to backup server
    print 'Exporting volume %s to backup server...' % destName
    lun_no = _3par.export_vv(destName, config.EXPORT_HOST)

    # discover volume
    print 'Volume is exported as LUN %d with WWN %s on %s. Discovering LUN...' % (lun_no, destWwn, config.EXPORT_HOST)
    subprocess.check_call('%s/sh/discover_lun.sh %d %s' % (base_path, lun_no, destWwn), shell=True)

    # restore voleme from backup
    print 'Restore volume from backup to exported lun'
    # calculate size
    size = destImage.SIZE * 1024 * 1024
    print subprocess.check_output('borg extract --stdout %s/%s::%s | pv -pterab -s %d | dd of=/dev/mapper/3%s bs=%s' % (config.BACKUP_PATH, srcImage.ID, args.datetime, size, destWwn, args.bs),
                                  shell=True)

    # flush volume
    print 'Flushing LUN...'
    subprocess.check_call('%s/sh/flush_lun.sh %s' % (base_path, destWwn), shell=True)

    # unexport volume
    print 'Unexporting volume %s from backup server...' % destName
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
    print ex
    exit(1)
