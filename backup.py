#!/usr/bin/env python

import logging
from multiprocessing import Pool
from multiprocessing_logging import install_mp_handler
import functions
import globals as g
from drivers import _3par

g.initialize()

# starting backup
if not g.args.pruneOnly:
    functions.send_email('Backup started! Images count: %d' % len(g.images))

# init logging
logging.basicConfig(level=logging.DEBUG)
install_mp_handler()
# init multi processing pool
pool = Pool(g.args.parallel)

results = pool.map(functions.backup_image, [image for key, image in sorted(g.images.iteritems())])

pool.close()

