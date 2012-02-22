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
import routes
import webob.exc

from novaclient.v1_1.client import Client
from reddwarf.common import config
from reddwarf.common import wsgi
from reddwarf.database import models
from reddwarf.database import views

LOG = logging.getLogger('reddwarf.database.service')


class BaseController(wsgi.Controller):
    """Base controller class."""

    def __init__(self):
        self.proxy_admin_user = config.Config.get('reddwarf_proxy_admin_user', 'admin')
        self.proxy_admin_pass = config.Config.get('reddwarf_proxy_admin_pass', '3de4922d8b6ac5a1aad9')
        self.proxy_admin_tenant_name = config.Config.get('reddwarf_proxy_admin_tenant_name', 'admin')
        self.auth_url = config.Config.get('reddwarf_auth_url', 'http://0.0.0.0:5000/v2.0')

    def get_client(self, req):
        proxy_token = req.headers["X-Auth-Token"]
        client = Client(self.proxy_admin_user, self.proxy_admin_pass,
            self.proxy_admin_tenant_name, self.auth_url, token=proxy_token)
        client.authenticate()
        return client

class InstanceController(BaseController):
    """Controller for instance functionality"""

    def index(self, req, tenant_id):
        """Return all instances."""
        servers = models.Instances(req.headers["X-Auth-Token"]).data()
        return wsgi.Result(views.InstancesView(servers).data(), 201)

    def show(self, req, tenant_id, id):
        """Return a single instance."""
        server = models.Instance(req.headers["X-Auth-Token"], id).data()
        return wsgi.Result(views.InstanceView(server).data(), 201)

    def create(self, req, body, tenant_id):
        server = self.get_client(req).servers.create(body['name'], body['image'], body['flavor'])
        LOG.info(server)
        return "server created %s" % server.__dict__


class API(wsgi.Router):
    """API"""
    def __init__(self):
        mapper = routes.Mapper()
        super(API, self).__init__(mapper)
        self._instance_router(mapper)

    def _instance_router(self, mapper):
        instance_resource = InstanceController().create_resource()
        path = "/{tenant_id}/instances"
        mapper.resource("instance", path, controller=instance_resource)


def app_factory(global_conf, **local_conf):
    return API()
