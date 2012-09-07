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


meta = MetaData()

security_group_instance_association = Table('security_group_instance_associations', meta,
    Column('id', String(36), primary_key=True, nullable=False),
    Column('security_group_id', String(36), nullable=False),
    Column('instance_id', String(36), nullable=False),
    Column('deleted', Boolean(), server_default=false()),
    Column('created_at', DateTime()),
    Column('updated_at', DateTime()),
    Column('deleted_at', DateTime()))

security_group_rules = Table('security_group_rules', meta,
    Column('id', String(36), primary_key=True, nullable=False),
    Column('protocol', String(length=255)),
    Column('cidr', String(length=255)),
    Column('from_port', String(length=255)),
    Column('to_port', String(length=255)),
    Column('security_group_id', String(length=36), nullable=False),
    Column('remote_secgroup_rule_id', String(length=36)),
    Column('deleted', Boolean(), server_default=false()),
    Column('created_at', DateTime()),
    Column('updated_at', DateTime()),
    Column('deleted_at', DateTime()))

security_groups = Table('security_groups', meta,
    Column('id', String(36), primary_key=True, nullable=False),
    Column('name', String(length=255), nullable=False),
    Column('description', String(length=255)),
    Column('remote_secgroup_id', String(length=36)),
    Column('user_id', String(length=255)),
    Column('tenant_id', String(length=255)),
    Column('availability_zone', String(length=255), nullable=false),
    Column('credential', String(length=36), nullable=false),
    Column('deleted', Boolean(), server_default=false()),
    Column('created_at', DateTime()),
    Column('updated_at', DateTime()),
    Column('deleted_at', DateTime()))

def upgrade(migrate_engine):
    meta.bind = migrate_engine
    create_tables([security_group_instance_association, security_group_rules, security_groups])


def downgrade(migrate_engine):
    meta.bind = migrate_engine
    drop_tables([security_group_instance_association, security_group_rules, security_groups ])