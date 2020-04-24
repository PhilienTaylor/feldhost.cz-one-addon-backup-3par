import os
import re
import subprocess
import sys
import time
from hpe3parclient import client, exceptions
from pyone import OneException

import config
import functions

base_path = os.path.abspath(os.path.dirname(sys.argv[0]))
cl = client.HPE3ParClient(config._3PAR['api'], False, config._3PAR['secure'], None, True)


def login():
    cl.setSSHOptions(config._3PAR['ip'], config._3PAR['username'], config._3PAR['password'])


def vv_name(source):
    ex = source.split(':')

    return ex[0]


def vv_name_wwn(source):
    ex = source.split(':')

    return ex[0], ex[1]


def create_snapshot_name(src_name, snap_id):
    name = '{srcName}.{snapId}'.format(srcName=src_name, snapId=snap_id)

    return name

def export_vv(name, host):
    # check if vlun already exists
    cmd = ['showvlun', '-v', name, '-host', host]
    vlunData = cl._run(cmd)

    if vlunData[0] == 'no vluns listed' or vlunData[1] == 'no vluns listed':
        # create export template
        cmd = ['createvlun', '-f', name, 'auto', host]
        cl._run(cmd)

        # get export lun number
        cmd = ['showvlun', '-v', name, '-host', host]
        vlunData = cl._run(cmd)

        if vlunData[0] == 'no vluns listed' or vlunData[1] == 'no vluns listed':
            print 'Can not export volume %s to host %s' % (name, host)
            exit(1)

    vlunData = vlunData[2].split(',')
    vlun = vlunData[0]

    return int(vlun)

def unexport_vv(name, host):
    # check if vlun aleready exists
    cmd = ['showvlun', '-v', name, '-host', host]
    vlunData = cl._run(cmd)

    vlun = 0
    index = 0
    for row in vlunData:
        index = index + 1
        if row.startswith('Lun'):
            # get LUN
            vlunData = vlunData[index].split(',')
            vlun = vlunData[0]
            break

    # lun doesnt exists, returning
    if vlun == 0:
        return

    # delete vlun
    cmd = ['removevlun', '-f', name, vlun, host]
    cl._run(cmd)

def backup_live(one, image, vm, vm_disk_id, verbose):
    # create live snapshot of image
    if verbose:
        print 'Creating live snapshot...'

    # we need to handle snapshot create errors, because if VM have more images, vm can be in state DISK_SNAPSHOT_DELETE
    # from previous image backup
    # TODO: we should snapshot all VM disks at one operation, to handle consistency across attached images
    done = False
    i = 0
    while not done:
        try:
            snap_id = one.vm.disksnapshotcreate(vm.ID, vm_disk_id, 'Automatic Backup')

            if snap_id is False:
                raise Exception('Error creating snapshot! Check VM logs.')

            done = True
        except OneException as ex:
            # failed after 3 times
            if i > 3:
                raise Exception(ex)
            i += 1
            time.sleep(5)


    # get source name and create snap name
    name = vv_name(image.SOURCE)
    snap_name = create_snapshot_name(name, snap_id)

    # wait until snapshot is created
    if verbose:
        print 'Waiting for snapshot to be created...'
    time.sleep(5)
    wwn = ''
    done = False
    i = 0
    while not done:
        # check if there is some soft-deleted snap
        cmd = ['showvv', '-showcols', 'VV_WWN,ExpirationTime', snap_name]
        vv = cl._run(cmd)

        if vv[1] != '---------------------':
            vv = vv[1].split(',')
            if vv[1] == '--':
               wwn = vv[0].lower()
               break

        # failed after 60s
        if i > 11:
            raise Exception('Looks like snapshot is not created. Check VM logs.')
        i += 1
        time.sleep(5)

    # export volume to backup server
    if verbose:
        print 'Snapshot %d:%s created.' % (snap_id, snap_name)
        print 'Exporting snapshot to backup server...'
    lun_no = export_vv(snap_name, config.EXPORT_HOST)

    if verbose:
        print 'Snapshot is exported as LUN %d with WWN %s on %s. Discovering LUN...' % (lun_no, wwn, config.EXPORT_HOST)

    # discover volume
    try:
        subprocess.check_call('%s/sh/discover_lun.sh %d %s' % (base_path, lun_no, wwn), shell=True)
    except subprocess.CalledProcessError as ex:
        raise Exception('Can not discover LUN', ex)

    # backup
    if verbose:
        print 'Backuping image....'
    dev = '/dev/mapper/3%s' % wwn
    result = borgbackup(name, dev, image.SIZE)
    if verbose:
        print result

    # flush volume
    if verbose:
        print 'Flushing LUN...'
    try:
        subprocess.check_call('%s/sh/flush_lun.sh %s' % (base_path, wwn), shell=True)
    except subprocess.CalledProcessError as ex:
        raise Exception('Can not flush LUN', ex)

    # unexport volume
    if verbose:
        print 'Unexporting snapshot from backup server...'
    unexport_vv(snap_name, config.EXPORT_HOST)

    # delete snapshot
    if verbose:
        print 'Deleting snapshot...'
    if not one.vm.disksnapshotdelete(vm.ID, vm_disk_id, snap_id):
        raise Exception('Can not delete snapshot! Check VM logs.')

    # prune old backups
    if verbose:
        print 'Pruning old backups...'
    result = borgprune(name)
    if verbose:
        print result


def backup(image, verbose):
    # get source name and wwn
    name, wwn = vv_name_wwn(image.SOURCE)

    # export volume to backup server
    if verbose:
        print 'Exporting volume %s to backup server...' % name
    lun_no = export_vv(name, config.EXPORT_HOST)

    if verbose:
        print 'Volume is exported as LUN %d with WWN %s on %s. Discovering LUN...' % (lun_no, wwn, config.EXPORT_HOST)

    # discover volume
    try:
        subprocess.check_call('%s/sh/discover_lun.sh %d %s' % (base_path, lun_no, wwn), shell=True)
    except subprocess.CalledProcessError as ex:
        raise Exception('Can not discover LUN', ex)

    # backup
    if verbose:
        print 'Backuping image....'
    dev = '/dev/mapper/3%s' % wwn
    result = borgbackup(name, dev, image.SIZE)
    if verbose:
        print result

    # flush volume
    if verbose:
        print 'Flushing LUN...'
    try:
        subprocess.check_call('%s/sh/flush_lun.sh %s' % (base_path, wwn), shell=True)
    except subprocess.CalledProcessError as ex:
        raise Exception('Can not flush LUN', ex)

    # unexport volume
    if verbose:
        print 'Unexporting volume %s from backup server...' % name
    unexport_vv(name, config.EXPORT_HOST)

    # prune old backups
    if verbose:
        print 'Pruning old backups...'
    result = borgprune(name)
    if verbose:
        print result


def prune(image, verbose):
    # get source name and wwn
    name, wwn = vv_name_wwn(image.SOURCE)

    # prune old backups
    if verbose:
        print 'Pruning old backups...'
    result = borgprune(name)
    if verbose:
        print result


def borgbackup(name, dev, size_mb):
    size = size_mb*1024*1024

    try:
        return subprocess.check_output('dd if=%s bs=256K | pv -pterab -s %d | borg create --compression auto,zstd,3 %s::%s-{now} -' % (dev, size, config.BACKUP_REPO, name), shell=True)
    except subprocess.CalledProcessError as ex:
        raise Exception('Can not backup dev using borgbackup!', ex)


def borgprune(name):
    # check if name is defined, prevent deleting more that we want
    if not re.match('^feldcloud\.one\.[0-9]+\.vv$', name):
        raise Exception('Can not run borg prune!', 'Name doesn\'t match pattern. Should be in format feldcloud.one.[0-9]+.vv, given "%s"' % name)

    try:
        return subprocess.check_output('borg prune -v --list --stats --keep-daily=7 --keep-weekly=4 --keep-monthly=6 --prefix=%s %s' % (name, config.BACKUP_REPO), shell=True)
    except subprocess.CalledProcessError as ex:
        raise Exception('Can not run borg prune!', ex)

