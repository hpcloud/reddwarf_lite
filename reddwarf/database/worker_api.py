# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 Hewlett-Packard Development Company, L.P.
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
Handles all request to the Platform Application Server
"""

import logging
import base64

from reddwarf.database import dbutils as utils
from reddwarf.rpc import impl_kombu as rpc


LOG = logging.getLogger(__name__)

class API():
    """API for interacting with the guest manager."""

#    def __init__(self, **kwargs):
#        super(API, self).__init__(**kwargs)

    def ensure_create_instance(self, context, instance, agent_config):
        LOG.debug("Triggering worker app server to ensure instance created: %s.", instance['id'])
        rpc.cast(context, 'work',
                 {"create-instance":{"uuid": instance['id'],
                                     "remoteUuid": instance['remote_uuid'],
                                     "remoteHostName": instance['remote_hostname'],
                                     "agentConfig": base64.b64encode(agent_config)}})
