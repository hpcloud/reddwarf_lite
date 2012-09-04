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
import eventlet

from reddwarf import db
from reddwarf.common import config
from reddwarf.common import context as rd_context
from reddwarf.common import errors
from reddwarf.common import exception
from reddwarf.common import result_state
from reddwarf.common import utils
from reddwarf.common import wsgi
from reddwarf.securitygroup import models
from reddwarf.securitygroup import views



CONFIG = config.Config
LOG = logging.getLogger(__name__)


class SecurityGroupController(wsgi.Controller):
    """Controller for security groups functionality"""
        
    def index(self, req, tenant_id):
        """Return all security groups tied to a particular tenant_id."""
        LOG.debug("Index() called with %s, %s" % (tenant_id, id))  

        context = req.context
        LOG.debug("Context: %s" % context.to_dict())

        sec_groups = models.SecurityGroup().find_all(tenant_id=tenant_id, deleted=False)
        LOG.debug(sec_groups)
        
        id_list = [sec_group['id'] for sec_group in sec_groups]
        #group_rules = models.SecurityGroupRule().find_all(deleted=False, models.SecurityGroupRule.security_group_id.in_(id_list))
        
        #rules_map = dict([(r.security_group_id, r) for r in group_rules])
        rules_map = None
        
        return wsgi.Result(views.SecurityGroupsView(sec_groups, rules_map, req, tenant_id).list(), 200)


    def show(self, req, tenant_id, id):
        """Return a single security group."""
        LOG.debug("Show() called with %s, %s" % (tenant_id, id))
        # TODO(hub-cap): turn this into middleware
        context = rd_context.ReddwarfContext(
                          auth_tok=req.headers["X-Auth-Token"],
                          tenant=tenant_id)
        LOG.debug("Context: %s" % context.to_dict())
        
        sec_group = models.SecurityGroup().find_by(id=id, tenant_id=tenant_id, deleted=False)
        group_rules = models.SecurityGroupRule().find_all(deleted=False, security_group_id=id)
        
        return wsgi.Result(views.SecurityGroupView(sec_group, group_rules, req, tenant_id).show(), 200)


    def delete(self, req, tenant_id, id):
        """Delete a single instance."""
        LOG.debug("Delete() called with %s, %s" % (tenant_id, id))
        # TODO(hub-cap): turn this into middleware
        context = rd_context.ReddwarfContext(
                          auth_tok=req.headers["X-Auth-Token"],
                          tenant=tenant_id)

        return wsgi.Result(None, 204)

    def create(self, req, body, tenant_id):
        
        LOG.info("Creating a database instance for tenant '%s'" % tenant_id)
        LOG.info("req : '%s'\n\n" % req)
        LOG.info("body : '%s'\n\n" % body)
        context = rd_context.ReddwarfContext(
                          auth_tok=req.headers["X-Auth-Token"],
                          tenant=tenant_id)
        
        
        return wsgi.Result(views.SecurityGroupView(sec_groups, req, tenant_id).create(), 201)
