# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright (c) 2011 OpenStack, LLC.
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

"""
Handles all request to the Platform or Guest VM
"""

from nova import flags
from nova import log as logging
from nova import rpc
from nova.db import api as nova_dbapi
from nova.db import base
from reddwarf.db import api as reddwarf_dbapi
from reddwarf import rpc as reddwarf_rpc
from reddwarf import exception


FLAGS = flags.FLAGS
LOG = logging.getLogger('nova.guest.api')


class API(base.Base):
    """API for interacting with the guest manager."""

    def __init__(self, **kwargs):
        super(API, self).__init__(**kwargs)

    def _get_routing_key(self, context, id):
        """Create the routing key based on the container id"""
        instance_ref = nova_dbapi.instance_get(context, id)
        return "guest.%s" % instance_ref['hostname'].split(".")[0]

    def create_user(self, context, id, users):
        """Make an asynchronous call to create a new database user"""
        LOG.debug("Creating Users for Instance %s", id)
        rpc.cast(context, self._get_routing_key(context, id),
                 {"method": "create_user",
                  "args": {"users": users}
                 })

    def list_users(self, context, id):
        """Make an asynchronous call to list database users"""
        LOG.debug("Listing Users for Instance %s", id)
        return rpc.call(context, self._get_routing_key(context, id),
                 {"method": "list_users"})

    def delete_user(self, context, id, user):
        """Make an asynchronous call to delete an existing database user"""
        LOG.debug("Deleting user %s for Instance %s",
                  user, id)
        rpc.cast(context, self._get_routing_key(context, id),
                 {"method": "delete_user",
                  "args": {"user": user}
                 })

    def create_database(self, context, id, databases):
        """Make an asynchronous call to create a new database
           within the specified container"""
        LOG.debug("Creating databases for Instance %s", id)
        rpc.cast(context, self._get_routing_key(context, id),
                 {"method": "create_database",
                  "args": {"databases": databases}
                 })

    def list_databases(self, context, id):
        """Make an asynchronous call to list database users"""
        LOG.debug("Listing Users for Instance %s", id)
        return rpc.call(context, self._get_routing_key(context, id),
                 {"method": "list_databases"})

    def delete_database(self, context, id, database):
        """Make an asynchronous call to delete an existing database
           within the specified container"""
        LOG.debug("Deleting database %s for Instance %s",
                  database, id)
        rpc.cast(context, self._get_routing_key(context, id),
                 {"method": "delete_instance",
                  "args": {"database": database}
                 })

    def enable_root(self, context, id):
        """Make a synchronous call to enable the root user for
           access from anywhere"""
        LOG.debug("Enable root user for Instance %s", id)
        return rpc.call(context, self._get_routing_key(context, id),
                 {"method": "enable_root"})

    def disable_root(self, context, id):
        """Make a synchronous call to disable the root user for
           access from anywhere"""
        LOG.debug("Disable root user for Instance %s", id)
        return rpc.call(context, self._get_routing_key(context, id),
                 {"method": "disable_root"})

    def is_root_enabled(self, context, id):
        """Make a synchronous call to check if root access is
           available for the container"""
        LOG.debug("Check root access for Instance %s", id)
        return rpc.call(context, self._get_routing_key(context, id),
                 {"method": "is_root_enabled"})

    def prepare(self, context, id, databases):
        """Make an asynchronous call to prepare the guest
           as a database container"""
        LOG.debug(_("Sending the call to prepare the Guest"))
        reddwarf_rpc.cast_with_consumer(context, self._get_routing_key(context, id),
                 {"method": "prepare",
                  "args": {"databases": databases}
                 })

    def upgrade(self, context, id):
        """Make an asynchronous call to self upgrade the guest agent"""
        topic = self._get_routing_key(context, id)
        LOG.debug("Sending an upgrade call to nova-guest %s", topic)
        reddwarf_rpc.cast_with_consumer(context, topic, {"method": "upgrade"})

    def check_mysql_status(self, context, id):
        """Make a synchronous call to trigger smart agent for checking MySQL status"""
        instance = reddwarf_dbapi.instance_from_uuid(id)
        LOG.debug("Triggering smart agent on Instance %s (%s) to check MySQL status.", id, instance['hostname'])
        result = rpc.call(context, instance['hostname'], {"method": "check_mysql_status"})
        # update instance state in guest_status table upon receiving smart agent response
        reddwarf_dbapi.guest_status_update(instance['internal_id'], int(result))
        return result

    def reset_password(self, context, id, password):
        """Make a synchronous call to trigger smart agent for resetting MySQL password"""
        instance = reddwarf_dbapi.instance_from_uuid(id)
        LOG.debug("Triggering smart agent to reset password on Instance %s (%s).", id, instance['hostname'])
        return rpc.call(context, instance['hostname'],
                {"method": "reset_password",
                 "args": {"password": password}})

    def create_snapshot(self, context, instance_id, snapshot_id, credential):
        LOG.debug("Triggering smart agent to create Snapshot %s on Instance %s.", snapshot_id, instance_id)
        instance = reddwarf_dbapi.instance_from_uuid(instance_id)
        rpc.cast(context, instance['hostname'],
                 {"method": "create_snapshot",
                  "args": {"sid": snapshot_id,
                           "credential": {"user": credential.user,
                                          "key": credential.key,
                                          "auth": credential.auth}}
                  })

    def apply_snapshot(self, context, instance_id, snapshot_id, credential):
        LOG.debug("Triggering smart agent to apply Snapshot %s on Instance %s.", snapshot_id, instance_id)
        instance = reddwarf_dbapi.instance_from_uuid(instance_id)
        snapshot = reddwarf_dbapi.db_snapshot_get(snapshot_id)
        rpc.cast(context, instance['hostname'],
                 {"method": "apply_snapshot",
                  "args": {"storage_path": snapshot['storage_uri'],
                           "credential": {"user": credential.user,
                                          "key": credential.key,
                                          "auth": credential.auth}}})


class PhoneHomeMessageHandler():
    """Proxy class to handle phone home messages sent from smart agent."""
    def __init__(self):
        self.msg_count = 0

    def __call__(self, msg):
        """Called by the phone home consumer whenever a message from smart agent is received."""
        self.msg_count += 1
        LOG.debug("Total number of phone home messages processed: %d", self.msg_count)
        self._validate(msg)

        # execute the requested method from the RPC message
        func = getattr(self, msg['method'], None)
        LOG.debug("Dispatching RPC method: %s", msg['method'])
        if callable(func):
            func(msg)

    def _validate(self, msg):
        """Validate that the request has all the required parameters"""
        if not msg:
            raise exception.NotFound("Phone home message is empty.")
        if not msg['method']:
            raise exception.NotFound("Required element/key 'method' was not specified in phone home message.")
        if not msg['args']:
            raise exception.NotFound("Required element/key 'args' was not specified in phone home message.")

    def update_instance_state(self, msg):
        """Update instance state in guest_status table."""
        # validate input message
        if not msg['args']['hostname']:
            raise exception.NotFound("Required element/key 'hostname' was not specified in phone home message.")
        if not msg['args']['state']:
            raise exception.NotFound("Required element/key 'state' was not specified in phone home message.")
        # update DB
        instance = reddwarf_dbapi.instance_from_hostname(msg['args']['hostname'])
        state = int(msg['args']['state'])
        LOG.debug("Updating mysql instance state for Instance %s", instance['uuid'])
        reddwarf_dbapi.guest_status_update(instance['internal_id'], state)

    def update_snapshot_state(self, msg):
        """Update snapshot state in database_snapshots table."""
        # validate input message
        if not msg['args']['sid']:
            raise exception.NotFound("Required element/key 'sid' was not specified in phone home message.")
        if '' == msg['args']['state']:
            raise exception.NotFound("Required element/key 'state' was not specified in phone home message.")
        if not msg['args']['storage_uri']:
            raise exception.NotFound("Required element/key 'storage_uri' was not specified in phone home message.")
        if '' == msg['args']['storage_size']:
            raise exception.NotFound("Required element/key 'storage_size' was not specified in phone home message.")
        # update DB
        reddwarf_dbapi.db_snapshot_update(msg['args']['sid'],
                                          msg['args']['state'],
                                          msg['args']['storage_uri'],
                                          msg['args']['storage_size'])