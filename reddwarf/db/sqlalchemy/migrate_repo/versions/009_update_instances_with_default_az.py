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
from sqlalchemy.sql.expression import null

from reddwarf.db.sqlalchemy.migrate_repo.schema import Table

def upgrade(migrate_engine):
    meta = MetaData(bind=migrate_engine)
    instances = Table('instances', meta, autoload=True)

    # Update existing records and set availability_zone = 'az2'
    conn = migrate_engine.connect()
    trans = conn.begin()
    try:
        update = instances.update().where(instances.c.availability_zone==null()).values(availability_zone='az-2.region-a.geo-1')
        conn.execute(update)
        trans.commit()
    except:
        trans.rollback()
        raise

    availability_zone = instances.c.availability_zone
    availability_zone.alter(nullable=False)


def downgrade(migrate_engine):
    meta = MetaData(bind=migrate_engine)
    instances = Table('instances', meta, autoload=True)
    availability_zone = instances.c.availability_zone
    availability_zone.alter(nullable=True)
