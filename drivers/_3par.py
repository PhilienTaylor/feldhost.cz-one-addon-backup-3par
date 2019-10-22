import time

from hpe3parclient import client, exceptions
import config

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


def backup_live(one, image, data_store, vm, vm_disk_id, verbose):
    # create live snapshot of image
    if verbose:
        print 'Creating live snapshot...'
    snap_id = one.vm.disksnapshotcreate(vm.ID, vm_disk_id, 'Automatic Backup')

    if snap_id is False:
        raise Exception('Error creating snapshot!')

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
                raise Exception('Looks like snapshot is not created. Investigate VM logs')
            i += 1
            time.sleep(5)

    # export VV to backup server
    if verbose:
        print 'Snapshot %d:%s created.' % (snap_id, snap_name)
        print 'Exporting snapshot to backup server...'
    lun_no = export_vv(snap_name, config.EXPORT_HOST)
    wwn = volume.get('wwn')

    if verbose:
        print 'Snapshot is exported as LUN %d with WWN %s on %s' % (lun_no, wwn, config.EXPORT_HOST)



