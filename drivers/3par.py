from hpe3parclient import client, exceptions
import config

# ------------------
# Login to 3PAR
# ------------------

cl = client.HPE3ParClient(config._3PAR['api'], config._3PAR['secure'])
cl.setSSHOptions(config._3PAR['ip'], config._3PAR['username'], config._3PAR['password'])

try:
    cl.login(config._3PAR['username'], config._3PAR['password'])
except exceptions.HTTPUnauthorized as ex:
    print "Login failed."

cl.logout()