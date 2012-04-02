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

import logging

from reddwarf.database import utils
from reddwarf.database import models
from reddwarf.database import views
from reddwarf.common import exception
from reddwarf.common import result_state
from reddwarf.rpc import impl_kombu as rpc


LOG = logging.getLogger(__name__)

class API():
    """API for interacting with the guest manager."""
    instance = {}

    def _get_routing_key(self, context, id):
        """Create the routing key based on the container id"""
        #instance_ref = nova_dbapi.instance_get(context, id)
        server = models.DBInstance().find_by(id=id)
        instance_ref = views.DBInstanceView(server).show()
        return "guest.%s" % instance_ref['instance']['remote_hostname'].split(".")[0]

    def upgrade(self, context, id):
        """Make an asynchronous call to self upgrade the guest agent"""
        topic = self._get_routing_key(context, id)
        LOG.debug("Sending an upgrade call to nova-guest %s", topic)
        #reddwarf_rpc.cast_with_consumer(context, topic, {"method": "upgrade"})
        rpc.cast(context, topic, {"method": "upgrade"})

    def check_mysql_status(self, context, id):
        """Make a synchronous call to trigger smart agent for checking MySQL status"""
        instance = utils.get_instance(id)
        LOG.debug("Triggering smart agent on Instance %s (%s) to check MySQL status.", id, instance['remote_hostname'])
        result = rpc.call(context, instance['remote_hostname'], {"method": "check_mysql_status"})
        # update instance state in guest_status table upon receiving smart agent response
        utils.update_guest_status(id, int(result))
        return result

    def reset_password(self, context, id, password):
        """Make a synchronous call to trigger smart agent for resetting MySQL password"""
        try:
            instance = utils.get_instance(id)
        except exception.ReddwarfError, e:
            return 404

        LOG.debug("Triggering smart agent to reset password on Instance %s (%s).", id, instance['remote_hostname'])
        try:
            return rpc.call(context, instance['remote_hostname'],
                {"method": "reset_password",
                 "args": {"password": password}})
        except Exception, e:
            return 500

    def create_snapshot(self, context, instance_id, snapshot_id, credential, auth_url):
        LOG.debug("Triggering smart agent to create Snapshot %s on Instance %s.", snapshot_id, instance_id)
        instance = utils.get_instance(instance_id)
        rpc.cast(context, instance['remote_hostname'],
                 {"method": "create_snapshot",
                  "args": {"sid": snapshot_id,
                           "credential": {"user": credential['tenant_id']+":"+credential['user_name'],
                                          "key": credential['password'],
                                          "auth": auth_url}}
                  })

    def apply_snapshot(self, context, instance_id, snapshot_id, credential, auth_url):
        LOG.debug("Triggering smart agent to apply Snapshot %s on Instance %s.", snapshot_id, instance_id)
        instance = utils.get_instance(instance_id)
        snapshot = utils.get_snapshot(snapshot_id)
        rpc.cast(context, instance['remote_hostname'],
                 {"method": "apply_snapshot",
                  "args": {"storage_path": snapshot['storage_uri'],
                           "credential": {"user": credential['tenant_id']+":"+credential['user_name'],
                                          "key": credential['password'],
                                          "auth": auth_url}}
                  })


class PhoneHomeMessageHandler():
    """Proxy class to handle phone home messages sent from smart agent."""
    def __init__(self):
        LOG.debug("PhoneHomeMessageHandler() init")
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
        instance = utils.get_instance_by_hostname(msg['args']['hostname'])
        state = result_state.ResultState().name(int(msg['args']['state']))
        LOG.debug("Updating mysql instance state for Instance %s", instance['id'])
        utils.update_guest_status(instance['id'], state)

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
        snapshot = utils.get_snapshot(msg['args']['sid'])
        LOG.debug("Updating snapshot state with ID %s", snapshot['id'])
        snapshot.update(storage_uri=msg['args']['storage_uri'],
                        storage_size=msg['args']['storage_size'],
                        state=result_state.ResultState().name(msg['args']['state']))
