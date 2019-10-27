#!/usr/bin/env python

import argparse
import subprocess
import time
import sys
import os

import config
import configmigrate
import pyone

base_path = os.path.abspath(os.path.dirname(sys.argv[0]))

# ----------------------------
# Define parser
# ----------------------------
parser = argparse.ArgumentParser(description='OpenNebula Migration Tool')

parser.add_argument('-i', '--image', help='Image ID in old cloud to migrate', type=int, required=True)

# -------------------------------------
# Parse args and proceed with execution
# -------------------------------------
args = parser.parse_args()


imageTypes = {0: 'OS', 1: 'CDROM', 2: 'DATABLOCK'}
imagePersistent = {0: 'NO', 1: 'YES'}

# -----------------------
# Connect to OpenNebula
# -----------------------
oneOld = pyone.OneServer(configmigrate.ONE['address'], session='%s:%s' % (configmigrate.ONE['username'], configmigrate.ONE['password']))
oneNew = pyone.OneServer(config.ONE['address'], session='%s:%s' % (config.ONE['username'], config.ONE['password']))

# find requested image
image = oneOld.image.info(args.image)

name = image.NAME.strip('_')
source = image.SOURCE

# allocate new image in datastore 101
template = 'NAME=%s TYPE=%s SIZE=%d PERSISTENT=%s DEV_PREFIX=sd DRIVER=raw' % (name, imageTypes[image.TYPE], image.SIZE, imagePersistent[image.PERSISTENT])
print template
id = oneNew.image.allocate(template, 101)

# get new image info
newSource = None
while not newSource:
    newImage = oneNew.image.info(id)
    newSource = newImage.SOURCE
    time.sleep(1)

print newSource

# copy image
print subprocess.check_output('nc -l -p 5000 | pv -pterab | dd of=/var/data/tmp/%s & ssh oneadmin@node1.feldhost.cz \'dd if=%s | nc -w 30 infra.feldcloud.net 5000\' ' % (name, source), shell=True)

# check img
print subprocess.check_output('qemu-img check /var/data/tmp/%s' % (name), shell=True)

# connect and login to 3PAR
from drivers import _3par
_3par.login()

# get vv name and wwn
vvname, wwn = _3par.vv_name_wwn(newSource)

# export volume to backup server
print 'Exporting volume %s to backup server...' % vvname
lun_no = _3par.export_vv(vvname, config.EXPORT_HOST)

# discover volume
print 'Volume is exported as LUN %d with WWN %s on %s. Discovering LUN...' % (lun_no, wwn, config.EXPORT_HOST)
subprocess.check_call('%s/sh/discover_lun.sh %d %s' % (base_path, lun_no, wwn), shell=True)

# covert qcow2 to raw directly to block device
print 'Convert qcow2 to raw and write to exported lun'
print subprocess.check_output('qemu-img convert -p -t none -O raw /var/data/tmp/%s /dev/mapper/3%s' % (name, wwn), shell=True)

# flush volume
print 'Flushing LUN...'
subprocess.check_call('%s/sh/flush_lun.sh %s' % (base_path, wwn), shell=True)

# unexport volume
print 'Unexporting volume %s from backup server...' % vvname
_3par.unexport_vv(vvname, config.EXPORT_HOST)

_3par.logout()
