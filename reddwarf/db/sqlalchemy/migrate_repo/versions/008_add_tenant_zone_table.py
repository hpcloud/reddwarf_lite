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

from reddwarf.db.sqlalchemy.migrate_repo.schema import Boolean
from reddwarf.db.sqlalchemy.migrate_repo.schema import create_tables
from reddwarf.db.sqlalchemy.migrate_repo.schema import DateTime
from reddwarf.db.sqlalchemy.migrate_repo.schema import drop_tables
from reddwarf.db.sqlalchemy.migrate_repo.schema import Integer
from reddwarf.db.sqlalchemy.migrate_repo.schema import BigInteger
from reddwarf.db.sqlalchemy.migrate_repo.schema import String
from reddwarf.db.sqlalchemy.migrate_repo.schema import Table
from sqlalchemy.sql.expression import false
import datetime



defaults = {
    'tenant_id': 'default_tenant',
    'availability_zone': 'az-2.region-a.geo-1'
}

meta = MetaData()

service_zones = Table('service_zones', meta,
    Column('id', String(36), primary_key=True, nullable=False),
    Column('service_name', String(255), nullable=False),
    Column('tenant_id', String(255), server_default=defaults['tenant_id'], nullable=False),
    Column('availability_zone', String(255), server_default=defaults['availability_zone'], nullable=False),
    Column('deleted', Boolean(), server_default=false(), nullable=False),
    Column('created_at', DateTime()),
    Column('updated_at', DateTime()),
    Column('deleted_at', DateTime())) 

def upgrade(migrate_engine):
    meta.bind = migrate_engine
    create_tables([service_zones, ])
    
    conn = migrate_engine.connect()
    trans = conn.begin()
    try:
        insert = service_zones.insert().values(id='1', 
                                               service_name='database', 
                                               tenant_id='default_tenant', 
                                               availability_zone=defaults['availability_zone'], 
                                               created_at=datetime.datetime.now())
        conn.execute(insert)
        trans.commit()
    except:
        trans.rollback()
        raise


def downgrade(migrate_engine):
    meta.bind = migrate_engine
    drop_tables([service_zones, ])
