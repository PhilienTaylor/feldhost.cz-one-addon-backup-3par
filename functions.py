import subprocess
import smtplib
import config


def bool_arg(string):
    if string != True and string != '1' and string != 'YES':
        return False
    return True


def list_of_int_arg(string):
    return map(int, string.split(','))


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

    # user specified start image id, so filter out all previous images
    if args.startImage:
        images = {}
        found = False
        for image_key in all_images:
            image = all_images[image_key]
            if not found and image.ID == args.startImage:
                found = True

            if found:
                images[image.ID] = image
        return images

    return all_images


def borgbackup_info():
    try:
        return subprocess.check_output('borg info %s' % (config.BACKUP_REPO), shell=True)
    except subprocess.CalledProcessError as ex:
        raise Exception('Can not issue borg info command on repo %s!' % (config.BACKUP_REPO), ex)

def send_email(log):
    msg = 'Subject: %s\n\n%s' % ('Cloud Backup Information', log)

    server = smtplib.SMTP("localhost", 25, )
    server.sendmail(config.EMAIL_SEND_FROM, config.EMAIL_SEND_TO, msg)
    server.quit()
