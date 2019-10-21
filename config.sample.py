# OpenNebula XML-RPC API connection details
ONE = {
    'address': 'https://opennebula:2633/RPC2',
    'username': 'user',
    'password': 'pass'
}

# Path where to save backups on backup server
BACKUP_DIR = '/var/data/backups/'

# Lock Image and VM during backup
# OpenNebula 5.6+ required
LOCK_RESOURCES = True

# 3PAR connection details
_3PAR = {
    'api': 'https://3par:8080/api/v1',
    'ip': '3par_ip',
    'username': '3paradm',
    'password': '3pardata',
    'secure': True
}
