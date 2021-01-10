# OpenNebula XML-RPC API connection details
ONE = {
    'address': 'https://opennebula:2633/RPC2',
    'username': 'user',
    'password': 'pass'
}

# Where to store borg backup repos
# each image have own repo automatically created
BACKUP_PATH = '/var/data/backups/'

# Lock Image and VM during backup
# OpenNebula 5.6+ required
LOCK_RESOURCES = True

# calls virsh domfstrim before snapshot is create
LIBVIRT_USE_DOMFSTRIM = True

# Libvirt hypervisor connection URI
# Only used if DOMFSTRIM is enabled
LIBVIRT_URI = 'qemu:///system'

# Path to private key file used to connect to compute nodes as oneadmin user
# Only used if DOMFSTRIM is enabled
SSH_IDENTITY_FILE = '/path/to/private.key'

# 3PAR connection details
_3PAR = {
    'api': 'https://3par:8080/api/v1',
    'ip': '3par_ip',
    'username': '3paradm',
    'password': '3pardata',
    'secure': True
}

# export volumes to host - backup host name defined in 3PAR
EXPORT_HOST = 'backup.hostname'

# email settings, we use local email server localhost:25
EMAIL_SEND_FROM = 'backup@domain.tld'
EMAIL_SEND_TO = 'admin@domain.tld'
