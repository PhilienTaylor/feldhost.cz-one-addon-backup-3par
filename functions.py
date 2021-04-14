import logging
import smtplib
import config
import datetime
import time
import subprocess
import globals as g
import pyone
from drivers import _3par

def bool_arg(string):
    if string != True and string != '1' and string != 'YES':
        return False
    return True


def list_of_int_arg(string):
    return list(map(int, string.split(',')))


def list_arg(string):
    return string.split(',')


def get_vm_hostname(vm):
    if isinstance(vm.HISTORY_RECORDS.HISTORY, list):
        return vm.HISTORY_RECORDS.HISTORY.pop().HOSTNAME

    return vm.HISTORY_RECORDS.HISTORY.HOSTNAME


def prepare_datastores(one, args):
    datastores = {}

    if args.datastore and len(args.datastore) == 1:
        datastore = one.datastore.info(args.datastore[0])
        datastores = {datastore.ID: datastore}
    else:
        datastore_pool = one.datastorepool.info()
        for datastore in datastore_pool.DATASTORE:
            if not args.datastore or datastore.ID in args.datastore:
                datastores[datastore.ID] = datastore

    return datastores


def prepare_images(one, args):
    images = {}

    if args.image and len(args.image) == 1:
        image = one.image.info(args.image[0])
        images = {image.ID: image}
    else:
        image_pool = one.imagepool.info(-2, -1, -1)
        for image in image_pool.IMAGE:
            if not args.image or image.ID in args.image:
                images[image.ID] = image

    return images


def filter_images(all_images, datastores, args):
    # filter images by datastores only if user limit by datastores arg
    if args.datastore:
        images = {}
        for image_key in all_images:
            image = all_images[image_key]
            if image.DATASTORE_ID in datastores:
                images[image.ID] = image

        all_images = images

    # filter by labels
    if args.label:
        images = {}
        for image_key in all_images:
            image = all_images[image_key]

            # image without lables, skipping
            if not 'LABELS' in image.TEMPLATE:
                continue

            # get image labels
            labels = list_arg(image.TEMPLATE['LABELS'])

            # search for requested labels in image labels
            for label in args.label:
                if label in labels:
                    images[image.ID] = image

        all_images = images

    # exclude by labels
    if args.exclude:
        images = {}
        for image_key in all_images:
            image = all_images[image_key]

            # image without lables, so not exclude
            if not 'LABELS' in image.TEMPLATE:
                images[image.ID] = image
                continue

            # get image labels
            labels = list_arg(image.TEMPLATE['LABELS'])

            # search for requested labels in image labels
            # if label not found, add image to list
            found = False
            for label in args.exclude:
                if label in labels:
                    found = True
                    break

            # no label found, adding
            if not found:
                images[image.ID] = image

        all_images = images

    return all_images


def send_email(log):
    msg = 'Subject: %s\n\n%s' % ('Cloud Backup Information', log)

    server = smtplib.SMTP("localhost", 25, )
    server.sendmail(config.EMAIL_SEND_FROM, config.EMAIL_SEND_TO, msg)
    server.quit()


def backup_image(image):
    datastore = g.datastores[image.DATASTORE_ID]

    # only datastores with 3PAR transfer manager
    if datastore.TM_MAD != '3par':
        return

    # ---------------------
    # Connect to OpenNebula
    # ---------------------
    one = pyone.OneServer(config.ONE['address'], session='%s:%s' % (config.ONE['username'], config.ONE['password']))

    # -------------------------
    # Connect and login to 3PAR
    # -------------------------
    _3par.login()

    # prune only?
    if g.args.pruneOnly:
        try:
            _3par.prune(image, g.args.verbose)
        except Exception as ex:
            logging.error(ex)
            send_email('Error prune image %d:%s: "%s"' % (image.ID, image.NAME, ex))
            # disconnect from 3PAR
            _3par.logout()
        return

    # mark start of backup in verbose output
    if g.args.verbose:
        logging.info('#============================================================')

    # set info abut backup start to image template
    try:
        one.image.update(image.ID,
                         'BACKUP_IN_PROGRESS=YES BACKUP_FINISHED_UNIX=--- BACKUP_FINISHED_HUMAN=--- BACKUP_STARTED_UNIX=%d BACKUP_STARTED_HUMAN="%s"' % (
                             int(time.time()), datetime.datetime.now().ctime()), 1)
    except Exception as ex:
        logging.error(ex)
        send_email('Error backup image %d:%s: "%s"' % (image.ID, image.NAME, ex))
        # disconnect from 3PAR
        _3par.logout()
        return

    # lock image
    if config.LOCK_RESOURCES:
        if g.args.verbose:
            logging.info('Locking image %d:%s' % (image.ID, image.NAME))
        one.image.lock(image.ID, 4)

    # persistent and attached to VM
    if image.PERSISTENT == 1 and image.RUNNING_VMS > 0:
        vmId = image.VMS.ID[0]
        vm = one.vm.info(vmId)
        vmDiskId = None

        if isinstance(vm.TEMPLATE.get('DISK'), list):
            for vmDisk in vm.TEMPLATE.get('DISK'):
                # volatile disks doesn't have IMAGE_ID attribute
                if vmDisk.get('IMAGE_ID') is not None and int(vmDisk.get('IMAGE_ID')) == image.ID:
                    vmDiskId = int(vmDisk.get('DISK_ID'))
                    break
        else:
            vmDiskId = int(vm.TEMPLATE.get('DISK').get('DISK_ID'))

        if vmDiskId is None:
            # error
            logging.warning('Can not found VM Disk ID for image %d:%s attached to VM %d:%s' % (
                image.ID, image.NAME, vmId, vm.NAME))
            send_email(
                'Can not found VM Disk ID for image %d:%s attached to VM %d:%s' % (image.ID, image.NAME, vmId, vm.NAME))
            # disconnect from 3PAR
            _3par.logout()
            return

        if g.args.verbose:
            logging.info('Backup persistent image %d:%s attached to VM %d:%s as disk %d' % (
                image.ID, image.NAME, vmId, vm.NAME, vmDiskId))

        # lock VM
        if config.LOCK_RESOURCES:
            if g.args.verbose:
                logging.info('Locking VM %d:%s' % (vmId, vm.NAME))
            one.vm.lock(vmId, 4)

        # execute filesystem trim command before actual backup
        if config.LIBVIRT_USE_DOMFSTRIM:
            if g.args.verbose:
                logging.info('Executing domfstrim on VM %d:%s and disk %d:%s' % (vmId, vm.NAME, image.ID, image.NAME))

            hostname = get_vm_hostname(vm)
            try:
                subprocess.check_call("ssh -i %s oneadmin@%s 'virsh -c %s domfstrim one-%d'" % (
                    config.SSH_IDENTITY_FILE, hostname, config.LIBVIRT_URI, vmId), shell=True)
            except Exception as ex:
                logging.error(ex)
                send_email('Error executing filesystem trim VM %d:%s and disk %d:%s: "%s"' % (vmId, vm.NAME, image.ID, image.NAME, ex))

        try:
            _3par.backup_live(one, image, vm, vmDiskId, g.args.verbose, g.args.bs)
        except Exception as ex:
            logging.error(ex)
            send_email('Error backup image %d:%s: "%s"' % (image.ID, image.NAME, ex))
            # disconnect from 3PAR
            _3par.logout()
            return

        # unlock VM
        if config.LOCK_RESOURCES:
            if g.args.verbose:
                logging.info('Unlocking VM %d:%s' % (vmId, vm.NAME))
            one.vm.unlock(vmId)

    # persistent not attached
    elif image.PERSISTENT == 1:
        if g.args.verbose:
            logging.info('Backup persistent not attached image %d:%s' % (image.ID, image.NAME))

        try:
            _3par.backup(image, g.args.verbose, g.args.bs)
        except Exception as ex:
            logging.error(ex)
            send_email('Error backup image %d:%s: "%s"' % (image.ID, image.NAME, ex))
            # disconnect from 3PAR
            _3par.logout()
            return

    # non-persistent
    elif image.PERSISTENT == 0:
        if g.args.verbose:
            logging.info('Backup non-persistent image %d:%s' % (image.ID, image.NAME))

        try:
            _3par.backup(image, g.args.verbose, g.args.bs)
        except Exception as ex:
            logging.error(ex)
            send_email('Error backup image %d:%s: "%s"' % (image.ID, image.NAME, ex))
            # disconnect from 3PAR
            _3par.logout()
            return

    # unlock image
    if config.LOCK_RESOURCES:
        if g.args.verbose:
            logging.info('Unlocking image %d:%s' % (image.ID, image.NAME))
        one.image.unlock(image.ID)

    # set info abut backup start to image template
    one.image.update(image.ID, 'BACKUP_IN_PROGRESS=NO BACKUP_FINISHED_UNIX=%d BACKUP_FINISHED_HUMAN="%s"' % (
        int(time.time()), datetime.datetime.now().ctime()), 1)

    # mark end of backup in verbose output
    if g.args.verbose:
        logging.info('#============================================================')

    # disconnect from 3PAR
    _3par.logout()

