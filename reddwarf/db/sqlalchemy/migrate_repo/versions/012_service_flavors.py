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


def upgrade(migrate_engine):
    meta = MetaData(bind=migrate_engine)
    service_flavors = Table('service_flavors', meta, autoload=True)
    ramc = Column('ram', Integer())
    ramc.create(service_flavors)
    vcpusc = Column('vcpus', Integer())
    vcpusc.create(service_flavors)


def downgrade(migrate_engine):
    meta = MetaData(bind=migrate_engine)
    service_flavors = Table('service_flavors', meta, autoload=True)
    service_flavors.c.ram.drop()
    service_flavors.c.vcpus.drop()
