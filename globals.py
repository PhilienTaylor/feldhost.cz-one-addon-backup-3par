import argparse
import config
import pyone
import functions

def initialize():
    # ----------------------------
    # Define parser
    # ----------------------------
    parser = argparse.ArgumentParser(description='OpenNebula Backup Tool')

    parser.add_argument('-i', '--image',
                        help='Image id or comma separated list of image ids to backup. Omit for backup all images',
                        type=functions.list_of_int_arg)
    parser.add_argument('-a', '--datastore',
                        help='Datastore id or comma separated list of datastore ids to backup from. Omit to backup from all datastores to backup',
                        type=functions.list_of_int_arg)
    parser.add_argument('-l', '--label', help='Label or comma separated list of labels of tagged images',
                        type=functions.list_arg)
    parser.add_argument('-e', '--exclude',
                        help='Skip (exclude) by label or comma separated list of labels of tagged images',
                        type=functions.list_arg)
    parser.add_argument('-P', '--pruneOnly', help='Don\'t backup anything, just prune old backups', action='store_true')
    parser.add_argument('-p', '--parallel', help='How much backup process can run in parallel, default 5', default=5,
                        type=int)
    parser.add_argument('-bs', '--bs', help='Define Block Size for DD command. Default 10M', default='10M')
    parser.add_argument('-D', '--deployments',
                        help='Not implemented yet! Backup also deployments files from system datastores',
                        action='store_true')
    parser.add_argument('-v', '--verbose', help='Verbose mode', action='store_true')

    # -------------------------------------
    # Parse args and proceed with execution
    # -------------------------------------
    global args
    args = parser.parse_args()

    # ---------------------
    # Connect to OpenNebula
    # ---------------------
    one = pyone.OneServer(config.ONE['address'], session='%s:%s' % (config.ONE['username'], config.ONE['password']))

    global datastores
    global images
    datastores = functions.prepare_datastores(one, args)
    all_images = functions.prepare_images(one, args)
    images = functions.filter_images(all_images, datastores, args)


