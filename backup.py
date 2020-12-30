#!/usr/bin/env python3

import logging
from multiprocessing import Pool
import functions
import globals as g

g.initialize()

# starting backup
if not g.args.pruneOnly:
    functions.send_email('Backup started! Images count: %d' % len(g.images))

# init logging
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# init multi processing pool
pool = Pool(g.args.parallel)

results = pool.map(functions.backup_image, [image for key, image in sorted(g.images.items())])

pool.close()

