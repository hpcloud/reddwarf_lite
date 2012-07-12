# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 Hewlett-Packard Development Company, L.P.
# Copyright 2011 OpenStack LLC.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from sqlalchemy import MetaData
from sqlalchemy import Table
from sqlalchemy import orm
from sqlalchemy.orm import exc as orm_exc


def map(engine, models):
    meta = MetaData()
    meta.bind = engine
    if mapping_exists(models['instance']):
        return

    orm.mapper(models['instance'], Table('instances', meta, autoload=True))
    orm.mapper(models['user'], Table('users', meta, autoload=True))
    orm.mapper(models['credential'], Table('credentials', meta, autoload=True))
    orm.mapper(models['guest_status'], Table('guest_status', meta, autoload=True))
    
    orm.mapper(models['service_image'],
               Table('service_images', meta, autoload=True))

    orm.mapper(models['service_flavor'],
               Table('service_flavors', meta, autoload=True))

    orm.mapper(models['service_secgroup'],
               Table('service_secgroups', meta, autoload=True))

    orm.mapper(models['snapshot'],
               Table('snapshots', meta, autoload=True))
    orm.mapper(models['quota'],
               Table('quotas', meta, autoload=True))

    orm.mapper(models['service_keypair'],
               Table('service_keypairs', meta, autoload=True))

    orm.mapper(models['service_zone'],
               Table('service_zones', meta, autoload=True))

    orm.mapper(models['volume'],
               Table('volumes', meta, autoload=True))

def mapping_exists(model):
    try:
        orm.class_mapper(model)
        return True
    except orm_exc.UnmappedClassError:
        return False
