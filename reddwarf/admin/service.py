# vim: tabstop=4 shiftwidth=4 softtabstop=4

#    Copyright 2012 Hewlett-Packard Development Company, L.P.
#
#    Copyright 2011 OpenStack LLC.
#    All Rights Reserved.
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
import urlparse
import routes
import webob.exc

from reddwarf.common import config
from reddwarf.common import context as rd_context
from reddwarf.common import exception
from reddwarf.common import utils
from reddwarf.common import wsgi
from reddwarf.admin import models

CONFIG = config.Config
LOG = logging.getLogger(__name__)


class BaseController(wsgi.Controller):
    """Base controller class."""

    exclude_attr = []
    exception_map = {
        webob.exc.HTTPUnprocessableEntity: [
            ],
        webob.exc.HTTPBadRequest: [
            models.InvalidModelError,
            ],
        webob.exc.HTTPNotFound: [
            exception.NotFound,
            models.ModelNotFoundError,
            ],
        webob.exc.HTTPConflict: [
            ],
        }

    def __init__(self):
        pass

    def _extract_required_params(self, params, model_name):
        params = params or {}
        model_params = params.get(model_name, {})
        return utils.stringify_keys(utils.exclude(model_params,
                                                  *self.exclude_attr))


class AdminController(BaseController):
    
    def validate(self, req, tenant_id):
        """Determine whether a user request has proper admin permissions."""
        context = rd_context.ReddwarfContext(
                          auth_tok=req.headers["X-Auth-Token"],
                          tenant=tenant_id)

        context = context.to_dict()
        LOG.debug("_validate() called with is_admin %s" % context['is_admin'])
        
        if bool(context['is_admin']):
            return True
        else:
            return False
    
    def agent(self, req, tenant_id, id):
        """Admin operations on the smart agent."""
        LOG.debug("Admin agent() called with %s, %s" % (tenant_id, id))
        
        if not self.validate(req, tenant_id):
             return wsgi.Result("Unauthorized", 401)
         
        return wsgi.Result(None, 200)
    
    def message_server(self, req, tenant_id, id):
        """Admin operations on the message server."""
        LOG.debug("Admin message_server() called with %s, %s" % (tenant_id, id))
        
        if not self.validate(req, tenant_id):
             return wsgi.Result("Unauthorized", 401)
         
        return wsgi.Result(None, 200)
    
    def database(self, req, tenant_id, id):
        """Admin operations on the database server."""
        LOG.debug("Admin database() called with %s, %s" % (tenant_id, id))
        
        if not self.validate(req, tenant_id):
             return wsgi.Result("Unauthorized", 401)
         
        return wsgi.Result(None, 200)
    
    def index_instances(self, req, tenant_id):
        return wsgi.Result(None, 200)
    
    def index_snapshots(self, req, tenant_id):
        return wsgi.Result(None, 200)
