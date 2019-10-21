#!/usr/bin/env python

import argparse
import urllib3

import config
import pyone
import functions

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ----------------------------
# Define parser
# ----------------------------
parser = argparse.ArgumentParser(description='OpenNebula Backup Tool')

parser.add_argument('-i', '--image', help='Image id or comma separated list of image ids to backup.'
                                                'Omit for backup all images', type=functions.list_of_int_arg)
parser.add_argument('-S', '--startImage', help='Image id to start backup from. Backups all following images'
                                                      'including defined one', type=int)
parser.add_argument('-a', '--datastore', help='Datastore id or comma separated list of datastore ids to backup'
                                                    'from. Omit to backup from all datastores to backup',
                    type=functions.list_of_int_arg)
parser.add_argument('-l', '--label', help='Label or comma separated list of labels of tagged images or datastores',
                    type=functions.list_arg)
parser.add_argument('-e', '--exclude', help='Skip (exclude) by label or comma separated list of labels of tagged'
                                                  'images or datastores', type=functions.list_arg)
parser.add_argument('-D', '--deployments', help='Backup also deployments files from system datastores')
parser.add_argument('-d', '--dryRun', help='Dry run - not execute any commands, all cmds will be just printed')
parser.add_argument('-v', '--verbose', help='Verbose mode')

# -------------------------------------
# Parse args and proceed with execution
# -------------------------------------
args = parser.parse_args()

# -----------------------
# Connect to OpenNebula
# -----------------------
one = pyone.OneServer(config.ONE['address'], session='%s:%s' % (config.ONE['username'], config.ONE['password']))

imagepool = one.imagepool.info(-2, -1, -1)

for image in imagepool.IMAGE:
    print image.PERSISTENT
