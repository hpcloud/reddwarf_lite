# vim: tabstop=4 shiftwidth=4 softtabstop=4

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

import logging
import webob.exc

from reddwarf.common import exception
from reddwarf.common import wsgi


LOG = logging.getLogger(__name__)


class RootController(wsgi.Controller):
    """Controller for instance functionality"""

    def index(self, req, tenant_id, instance_id):
        raise exception.NotImplemented(_("Not implemented"))


    def create(self, req, body, tenant_id, instance_id):
        raise exception.NotImplemented(_("Not implemented"))

class UserController(wsgi.Controller):
    """Controller for instance functionality"""

    def index(self, req, tenant_id, instance_id):
        raise exception.NotImplemented(_("Not implemented"))

    def create(self, req, body, tenant_id, instance_id):
        raise exception.NotImplemented(_("Not implemented"))
    
    def delete(self, req, tenant_id, instance_id, id):
        raise exception.NotImplemented(_("Not implemented"))
    
    def show(self, req, tenant_id, instance_id, id):
        raise exception.NotImplemented(_("Not implemented"))

class SchemaController(wsgi.Controller):
    """Controller for instance functionality"""

    def index(self, req, tenant_id, instance_id):
        raise exception.NotImplemented(_("Not implemented"))
    
    def create(self, req, body, tenant_id, instance_id):
        raise exception.NotImplemented(_("Not implemented"))
    
    def delete(self, req, tenant_id, instance_id, id):
        raise exception.NotImplemented(_("Not implemented"))
    
    def show(self, req, tenant_id, instance_id, id):
        raise exception.NotImplemented(_("Not implemented"))
