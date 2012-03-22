# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 HP Software, LLC
# All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

"""Proxy classes to handle messages coming from remote agent in a passive mode."""

import logging
import threading

from reddwarf.rpc import impl_kombu
from reddwarf.database import guest_api as guest_api

#CONFIG = config.Config
LOG = logging.getLogger(__name__)

EXCHANGE = "phonehome"

class MessageHandlerService(threading.Thread):
    """A background service to listen on MQ and handle messages pushed from remote agents.
       It will be started on an independent thread living through the API Server lifetime."""
       
    def __init__ (self):
        threading.Thread.__init__(self)
        LOG.info("MessageHandler init")
        self._listener = None
        self._msg_handler = guest_api.PhoneHomeMessageHandler()
        
    def run(self):
        """Setup connection to MQ with one single consumer to handle
           phone home messages from all remote instances"""
        LOG.debug("Starting Message Handler Service...")
        self._listener = impl_kombu.listen(EXCHANGE, self._msg_handler)
        LOG.debug("Created listener")

    def stop(self):
        """Close consumer to MQ"""
        self._listener.done()
        LOG.debug("Message Handler Service is stopped.")