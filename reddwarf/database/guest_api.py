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

from reddwarf.database import dbutils
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
        instance = dbutils.get_instance(id)
        LOG.debug("Triggering smart agent on Instance %s (%s) to check MySQL status.", id, instance['remote_hostname'])
        result = rpc.call(context, instance['remote_hostname'], {"method": "check_mysql_status"})
        # update instance state in guest_status table upon receiving smart agent response
        dbutils.update_guest_status(id, int(result))
        return result

    def reset_password(self, context, id, password):
        """Make a synchronous call to trigger smart agent for resetting MySQL password"""
        try:
            instance = dbutils.get_instance(id)
        except exception.ReddwarfError, e:
            raise exception.NotFound("Instance with id %s not found", id)

        LOG.debug("Triggering smart agent to reset password on Instance %s (%s).", id, instance['remote_hostname'])
        return rpc.call(context, instance['remote_hostname'],
                {"method": "reset_password", "args": {"password": password}})

    def create_snapshot(self, context, instance_id, snapshot_id, credential, auth_url, snapshot_key):
        LOG.debug("Triggering smart agent to create Snapshot %s on Instance %s.", snapshot_id, instance_id)
        instance = dbutils.get_instance(instance_id)
        rpc.cast(context, instance['remote_hostname'],
                 {"method": "create_snapshot",
                  "args": {"sid": snapshot_id,
                           "tenant_id": context.tenant,
                           "snapshot_key": snapshot_key,
                           "credential": {"user": credential['tenant_id']+":"+credential['user_name'],
                                          "key": credential['password'],
                                          "auth": auth_url}}
                  })

    def apply_snapshot(self, context, instance_id, snapshot_id, credential, auth_url):
        LOG.debug("Triggering smart agent to apply Snapshot %s on Instance %s.", snapshot_id, instance_id)
        instance = dbutils.get_instance(instance_id)
        snapshot = dbutils.get_snapshot(snapshot_id)
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
        LOG.info("Processing message %d: %s", self.msg_count, msg)
        try:
            self._validate(msg)
            # execute the requested method from the RPC message
            func = getattr(self, msg['method'], None)
            LOG.debug("Dispatching RPC method: %s", msg['method'])
            if callable(func):
                func(msg)
        except Exception as e:
            LOG.error("Error processing phone home message: %s", e)
            pass

    def _validate(self, msg):
        """Validate that the request has all the required parameters"""
        LOG.debug("Validating RPC Message: %s", msg)
        if not msg:
            raise exception.NotFound("Phone home message is empty.")
        if not msg['method']:
            raise exception.NotFound("Required element/key 'method' was not specified in phone home message.")
        if not msg['args']:
            raise exception.NotFound("Required element/key 'args' was not specified in phone home message.")

    def _extract_public_ip(self, remote_server):
        adds = remote_server['addresses']['private']
        for address in adds:
            if address['addr'].startswith('15.185'):
                public_ip = address['addr']
                break;
            
        return public_ip
        
    def update_instance_state(self, msg):
        """Update instance state in guest_status table."""
        LOG.debug("Updating instance state: %s", msg)
        # validate input message
        if not msg['args']['hostname']:
            raise exception.NotFound("Required element/key 'hostname' was not specified in phone home message.")
        if '' == msg['args']['state']:
            raise exception.NotFound("Required element/key 'state' was not specified in phone home message.")

        # update DB
        instance = dbutils.get_instance_by_hostname(msg['args']['hostname'])
        state = result_state.ResultState().name(int(msg['args']['state']))
        
        # Treat running and success the same
        if state == 'running' or state == 'success':
            state = 'running'
        
        credential_id = instance['credential']
        region = instance['availability_zone']
        remote_uuid = instance['remote_uuid']
        
        if instance['address'] is None:
            # Look up the public_ip for nova instance
            credential = models.Credential.find_by(id=credential_id)
            try:
                remote_instance = models.Instance(credential=credential, region=region, uuid=remote_uuid)

                # as of Oct 24, 2012, the phonehomehandler has not be executed anymore, app server does all the updates towards api db
                public_ip = self._extract_public_ip(remote_instance.data())
                LOG.debug("Updating Instance %s with IP: %s" % (instance['id'], public_ip))

                dbutils.update_instance_with_ip(instance['id'], public_ip)
            except exception.NotFound:
                LOG.warn("Unable to find Remote instance and extract public ip")
            except exception.ReddwarfError:
                LOG.exception("Error occurred updating instance with public ip")

        LOG.debug("Updating mysql instance state for Instance %s", instance['id'])
        dbutils.update_guest_status(instance['id'], state)
        
    
    def update_snapshot_state(self, msg):
        """Update snapshot state in database_snapshots table."""
        LOG.debug("Updating snapshot state: %s", msg)

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
        snapshot = dbutils.get_snapshot(msg['args']['sid'])
        LOG.debug("Updating snapshot state with ID %s", snapshot['id'])
        snapshot.update(storage_uri=msg['args']['storage_uri'],
                        storage_size=msg['args']['storage_size'],
                        state=result_state.ResultState().name(msg['args']['state']))
