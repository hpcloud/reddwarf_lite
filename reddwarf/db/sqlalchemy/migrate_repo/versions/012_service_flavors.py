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

import datetime

from sqlalchemy import ForeignKey
from sqlalchemy.schema import Column
from sqlalchemy.schema import MetaData
from sqlalchemy.schema import UniqueConstraint
from sqlalchemy.sql import func as mysql_func
from sqlalchemy.sql.expression import false

from reddwarf.db.sqlalchemy.migrate_repo.schema import Boolean
from reddwarf.db.sqlalchemy.migrate_repo.schema import create_tables
from reddwarf.db.sqlalchemy.migrate_repo.schema import DateTime
from reddwarf.db.sqlalchemy.migrate_repo.schema import drop_tables
from reddwarf.db.sqlalchemy.migrate_repo.schema import Integer
from reddwarf.db.sqlalchemy.migrate_repo.schema import BigInteger
from reddwarf.db.sqlalchemy.migrate_repo.schema import String
from reddwarf.db.sqlalchemy.migrate_repo.schema import Table


SERVICE_FLAVORS = [
    {"id": "0", "flavor_name": "xsmall", "flavor_id": "100", "ram": 1, "vcpus": 1},
    {"id": "1", "flavor_name": "small", "flavor_id": "101", "ram": 2, "vcpus": 2},
    {"id": "2", "flavor_name": "medium", "flavor_id": "102", "ram": 4, "vcpus": 2},    
    {"id": "3", "flavor_name": "large", "flavor_id": "103", "ram": 8, "vcpus": 4},
    {"id": "4", "flavor_name": "xlarge", "flavor_id": "104", "ram": 16, "vcpus": 4},
    {"id": "5", "flavor_name": "2xlarge", "flavor_id": "105", "ram": 32, "vcpus": 8}
]

def upgrade(migrate_engine):
    meta = MetaData(bind=migrate_engine)
    service_flavors = Table('service_flavors', meta, autoload=True)
    
    conn = migrate_engine.connect()
    trans = conn.begin()
    try:
        delete = service_flavors.delete()\
                                .where(service_flavors.c.service_name=='database')
        conn.execute(delete)
        trans.commit()
    except:
        trans.rollback()
        raise
    
    ramc = Column('ram', Integer())
    ramc.create(service_flavors)
    vcpusc = Column('vcpus', Integer())
    vcpusc.create(service_flavors)
    
    conn = migrate_engine.connect()
    trans = conn.begin()
    try:
        for flavor in SERVICE_FLAVORS:
            insert = service_flavors.insert()\
                .execute(id=flavor['id'], service_name="database", flavor_name=flavor['flavor_name'], 
                        flavor_id=flavor['flavor_id'], deleted=0, ram=flavor['ram'], 
                        vcpus=flavor['vcpus'], created_at=datetime.datetime.now(), updated_at=datetime.datetime.now())
            trans.commit
    except:
        trans.rollback()
        raise

def downgrade(migrate_engine):
    meta = MetaData(bind=migrate_engine)
    service_flavors = Table('service_flavors', meta, autoload=True)
    
    conn = migrate_engine.connect()
    trans = conn.begin()
    try:
        delete = service_flavors.delete()\
                                .where(service_flavors.c.service_name=='database')
        conn.execute(delete)
        trans.commit()
    except:
        trans.rollback()
        raise    
    
    service_flavors.c.ram.drop()
    service_flavors.c.vcpus.drop()
    
    try:
        insert = service_flavors.insert()\
            .execute(id="3", service_name="database", flavor_name="large", 
                    flavor_id="103", deleted=0, created_at=datetime.datetime.now(), 
                    updated_at=datetime.datetime.now())
        trans.commit
    except:
        trans.rollback()
        raise
