# vim: tabstop=4 shiftwidth=4 softtabstop=4

#    Copyright 2012 Hewlett-Packard Development Company, L.P.
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
import routes
import urlparse
import webob.exc

from reddwarf import rpc
from reddwarf.common import config
from reddwarf.common import context as rd_context
from reddwarf.common import exception
from reddwarf.common import utils
from reddwarf.common import wsgi
from reddwarf.database import models
from reddwarf.database import views

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


class RootController(BaseController):
    """Controller for root functionality"""

    def is_root_enabled(self, req, tenant_id, id):
        """Return whether root is enabled on an instance."""
        LOG.debug("Called is_root_enabled()")
        
        return wsgi.Result(200)
    
    def create(self, req, tenant_id, id):
        """Enable the root user for an instance."""
        LOG.debug("Called create() for root")
        
        return wsgi.Result(201)