# OpenNebula Backup Tool for 3PAR storage driver

## Description

Purpose of this script is to backup OpenNebula datastores of type 3PAR.
This script have to run on dedicated backup server.

It backups:
- non-persistent base images - those which are used to deploy non-persistent VMs
- persistent images with live snapshoting support
    - when image is attached to VM them live snapshot is created
    - them image is exported to backup server over Fiber-Channel and backuped using BorgBackup
    - at the end snapshot is deleted
- system datastores with deployments files - without VM images, which are non-persistent ones

## How it works

![Flow diagram](https://gitlab.feldhost.cz/feldhost-public/one-addon-backup-3par/raw/master/images/how-it-works.svg) 

## Development

To contribute bug patches or new features, you can use the github Pull Request model. It is assumed that code and documentation are contributed under the Apache License 2.0.

More info:

* [How to Contribute](http://opennebula.org/addons/contribute/)
* Support: [OpenNebula user forum](https://forum.opennebula.org/c/support)
* Development: [OpenNebula developers forum](https://forum.opennebula.org/c/development)
* Issues Tracking: [Gitlab issues](https://gitlab.feldhost.cz/feldhost-public/one-addon-backup-3par/issues)

## Authors

* Leader: Kristian Feldsam (feldsam@feldhost.net)

## Support

[FeldHost™ as OpenNebula Systems Service Partner](https://www.feldhost.net/products/opennebula) offers design, implementation, operation and management of a cloud solution based on OpenNebula.

