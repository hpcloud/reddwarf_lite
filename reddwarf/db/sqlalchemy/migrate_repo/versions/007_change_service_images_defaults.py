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

from sqlalchemy import ForeignKey
from sqlalchemy.schema import Column
from sqlalchemy.schema import MetaData
from sqlalchemy.schema import UniqueConstraint
from sqlalchemy.sql.expression import text

from reddwarf.db.sqlalchemy.migrate_repo.schema import Table

defaults = {
    'tenant_id': {
        'old': text('NULL'),
        'new': 'default_tenant'
    },
    'availability_zone': {
        'old': text('NULL'),
        'new': 'az-2.region-a.geo-1'
    }
}

def upgrade(migrate_engine):
    print dir(migrate_engine)
    meta = MetaData(bind=migrate_engine)
    service_images = Table('service_images', meta, autoload=True)
    tenant_id = service_images.c.tenant_id
    tenant_id.alter(server_default=defaults['tenant_id']['new'], nullable=False)
    availability_zone = service_images.c.availability_zone
    availability_zone.alter(server_default=defaults['availability_zone']['new'], nullable=False)

    conn = migrate_engine.connect()
    trans = conn.begin()
    try:
      update = service_images.update()\
                             .where(service_images.c.tenant_id=='' and service_images.c.availability_zone=='')\
                             .values(tenant_id=defaults['tenant_id']['new'], availability_zone=defaults['availability_zone']['new'])
      conn.execute(update)
      trans.commit()
    except:
      trans.rollback()
      raise

def downgrade(migrate_engine):
    meta = MetaData(bind=migrate_engine)
    service_images = Table('service_images', meta, autoload=True)
    tenant_id = service_images.c.tenant_id
    tenant_id.alter(server_default=defaults['tenant_id']['old'], nullable=True)
    availability_zone = service_images.c.availability_zone
    availability_zone.alter(server_default=defaults['availability_zone']['old'], nullable=True)

    conn = migrate_engine.connect()
    trans = conn.begin()
    try:
      update = service_images.update()\
                             .where(service_images.c.tenant_id==defaults['tenant_id']['new'] and service_images.c.availability_zone==defaults['availability_zone']['new'])\
                             .values(tenant_id=defaults['tenant_id']['old'], availability_zone=defaults['availability_zone']['old'])
      conn.execute(update)
      trans.commit()
    except:
      trans.rollback()
      raise

