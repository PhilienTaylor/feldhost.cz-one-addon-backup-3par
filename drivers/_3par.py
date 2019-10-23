import os
import subprocess
import sys
import time
from hpe3parclient import client, exceptions
import config

base_path = os.path.abspath(os.path.dirname(sys.argv[0]))
cl = client.HPE3ParClient(config._3PAR['api'], False, config._3PAR['secure'], None, True)


def login():
    cl.setSSHOptions(config._3PAR['ip'], config._3PAR['username'], config._3PAR['password'])

    try:
        cl.login(config._3PAR['username'], config._3PAR['password'])
    except exceptions.HTTPUnauthorized:
        print "Login failed."


def logout():
    cl.logout()


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
    # check if VLUN already exists
    try:
        vluns = cl.getHostVLUNs(host)
        for vlun in vluns:
            if vlun.get('volumeName') == name:
                return int(vlun.get('lun'))
    except exceptions.HTTPNotFound:
        pass

    # create VLUN
    done = False
    while not done:
        try:
            location = cl.createVLUN(name, None, host, None, None, None, True)
            return int(location.split(',')[1])
        except exceptions.HTTPConflict:
            time.sleep(5)


def unexport_vv(name, host):
    # check if VLUN exists
    found = False
    vluns = cl.getHostVLUNs(host)
    for vlun in vluns:
        if vlun.get('volumeName') == name:
            found = True
            break

    if found == False:
        return

    cl.deleteVLUN(name, vlun.get('lun'), host)


def backup_live(one, image, vm, vm_disk_id, verbose):
    # create live snapshot of image
    if verbose:
        print 'Creating live snapshot...'
    snap_id = one.vm.disksnapshotcreate(vm.ID, vm_disk_id, 'Automatic Backup')

    if snap_id is False:
        raise Exception('Error creating snapshot! Check VM logs.')

    # get source name and create snap name
    name = vv_name(image.SOURCE)
    snap_name = create_snapshot_name(name, snap_id)

    # wait until snapshot is created
    if verbose:
        print 'Waiting for snapshot to be created...'
    time.sleep(5)
    done = False
    i = 0
    while not done:
        try:
            volume = cl.getVolume(snap_name)
            done = True
        except exceptions.HTTPNotFound:
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
    wwn = volume.get('wwn').lower()

    if verbose:
        print 'Snapshot is exported as LUN %d with WWN %s on %s. Discovering LUN...' % (lun_no, wwn, config.EXPORT_HOST)

    # discover volume
    try:
        subprocess.check_call('%s/sh/discover_lun.sh %d %s' % (base_path, lun_no, wwn), shell=True)
    except subprocess.CalledProcessError as ex:
        raise Exception('Can not discover LUN', ex)

    # backup
    # TODO
    if verbose:
        print 'TODO: Backuping image....'

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
    # TODO
    if verbose:
        print 'TODO: Backuping image....'

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
