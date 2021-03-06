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


meta = MetaData()

instances = Table('instances', meta,
        Column('id', String(36), primary_key=True, nullable=False),
        Column('name', String(255)),
        Column('status', String(255)),
        Column('remote_id', BigInteger()),
        Column('remote_uuid', String(36)),
        Column('remote_hostname', String(36)),
        Column('user_id', String(36)),
        Column('tenant_id', String(36)),
        Column('credential', String(36)),
        Column('address', String(255)),
        Column('port', Integer()),
        Column('flavor', Integer()),
        Column('availability_zone', String(255)),
        Column('deleted', Boolean()),
        Column('created_at', DateTime()),
        Column('updated_at', DateTime()),
        Column('deleted_at', DateTime()))

users = Table('users', meta,
        Column('id', String(36), primary_key=True, nullable=False),
        Column('name', String(255), nullable=False),
        Column('enabled', Boolean()),
        Column('deleted', Boolean()),
        Column('created_at', DateTime()),
        Column('updated_at', DateTime()),
        Column('deleted_at', DateTime()))

credentials = Table('credentials', meta,
        Column('id', String(36), primary_key=True, nullable=False),
        Column('user_name', String(255), nullable=False),
        Column('password', String(255), nullable=False),
        Column('tenant_id', String(255), nullable=False),
        Column('type', String(20)),
        Column('enabled', Boolean()),
        Column('deleted', Boolean()),
        Column('created_at', DateTime()),
        Column('updated_at', DateTime()),
        Column('deleted_at', DateTime()))

guest_status = Table('guest_status', meta,
        Column('id', String(36), primary_key=True, nullable=False),
        Column('instance_id', String(36)),
        Column('state', String(32)),
        Column('deleted', Boolean()),
        Column('created_at', DateTime()),
        Column('updated_at', DateTime()),
        Column('deleted_at', DateTime()))                    
                 

def upgrade(migrate_engine):
    meta.bind = migrate_engine
    create_tables([instances, users, credentials, guest_status, ])


def downgrade(migrate_engine):
    meta.bind = migrate_engine
    drop_tables([instances, users, credentials, guest_status, ])
