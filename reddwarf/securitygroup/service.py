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
from reddwarf.database import models as instance_models
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

        context = rd_context.ReddwarfContext(
                          auth_tok=req.headers["X-Auth-Token"],
                          tenant=tenant_id)

        sec_group = models.SecurityGroup.find_by(id=id, tenant_id=tenant_id, deleted=False)
        
        try:
            credential = instance_models.Credential().find_by(id=sec_group['credential'])
            models.RemoteSecurityGroup.delete(credential, sec_group['availability_zone'], sec_group['remote_secgroup_id'])
            sec_group.delete()
        except exception.ReddwarfError, e:
            LOG.exception('Failed to delete security group')
            raise exception.ReddwarfError("Failed to delete Security Group")
        
        return wsgi.Result(None, 204)

    def create(self, req, body, tenant_id):
        
        LOG.info("Creating a database instance for tenant '%s'" % tenant_id)
        LOG.info("req : '%s'\n\n" % req)
        LOG.info("body : '%s'\n\n" % body)
        context = rd_context.ReddwarfContext(
                          auth_tok=req.headers["X-Auth-Token"],
                          tenant=tenant_id)
        
        self.validate(body)

        # Get the credential to use for proxy compute resource
        credential = instance_models.Credential.find_by(type='compute', deleted=False)

        try:
            service_zone = instance_models.ServiceZone.find_by(service_name='database', tenant_id=tenant_id, deleted=False)
        except exception.ModelNotFoundError, e:
            LOG.info("Service Zone for tenant %s not found, using zone for 'default_tenant'" % tenant_id)
            service_zone = instance_models.ServiceZone.find_by(service_name='database', tenant_id='default_tenant', deleted=False)

        region_az = service_zone['availability_zone']
        
        description = body['security_group'].get('description', None)

        sec_group = self._try_create_secgroup(context, credential, region_az, body['security_group']['name'], description)
        
        return wsgi.Result(views.SecurityGroupView(sec_group, None, req, tenant_id).create(), 201)


    def _try_create_secgroup(self, context, credential, region, name, description):
        remote_name = 'dbaas-' + utils.generate_uuid()
        try:
            remote_sec_group = models.RemoteSecurityGroup.create(credential=credential, 
                                                                 region=region, 
                                                                 name=remote_name, 
                                                                 description=description)
            
            if not remote_sec_group:
                raise exception.ReddwarfError("Failed to create Security Group")
            else:
                # Create db record
                sec_group = models.SecurityGroup.create(name=name,
                                                        description=description,
                                                        remote_secgroup_id=remote_sec_group.data()['id'],
                                                        user_id=context.user,
                                                        tenant_id=context.tenant,
                                                        credential=credential['id'],
                                                        availability_zone=region)
                return sec_group
        except exception.SecurityGroupCreationFailure, e:
            LOG.exception("Failed to create remote security group")
            raise exception.ReddwarfError("Failed to create Security Group")

        

    def validate(self, body):
        try:
            body['security_group']
            body['security_group']['name']
            body['security_group']['description']
        except KeyError as e:
            LOG.error(_("Create Security Group Required field(s) - %s") % e)
            raise exception.ReddwarfError("Required element/key - %s "
                                       "was not specified" % e)
        
        

class SecurityGroupRuleController(wsgi.Controller):
    """Controller for security group rule functionality"""        

    def delete(self, req, tenant_id, id):
        LOG.debug("Delete Security Group called with %s, %s" % (tenant_id, id))

        context = rd_context.ReddwarfContext(
                          auth_tok=req.headers["X-Auth-Token"],
                          tenant=tenant_id)

        sec_group_rule = models.SecurityGroupRule.find_by(id=id, deleted=False)
        sec_group = models.SecurityGroup.find_by(id=sec_group_rule['security_group_id'], tenant_id=tenant_id, deleted=False)
        
        if sec_group is None:
            LOG.error("Attempting to delete Group Rule that does not belong to tenant %s" % tenant_id)
            raise exception.Forbidden("Unauthorized")
        
        try:
            credential = instance_models.Credential().find_by(id=sec_group['credential'])
            models.RemoteSecurityGroup.delete_rule(credential, sec_group['availability_zone'], id)
            sec_group_rule.delete()
        except exception.ReddwarfError, e:
            LOG.exception('Failed to delete security group')
            raise exception.ServerError("Failed to delete Security Group")
        
        return wsgi.Result(None, 204)

    def create(self, req, body, tenant_id):
        
        LOG.debug("Creating a Security Group Rule for tenant '%s'" % tenant_id)
        context = rd_context.ReddwarfContext(
                          auth_tok=req.headers["X-Auth-Token"],
                          tenant=tenant_id)
        
        self.validate(body)

        sec_group_id = body['security_group_rule']['security_group_id']
        
        sec_group = models.SecurityGroup.find_by(id=sec_group_id, tenant_id=tenant_id, deleted=False)

        credential = instance_models.Credential.find_by(id=sec_group['credential'])
        region_az = sec_group['availability_zone']
        
        cidr = body['security_group_rule']['cidr']
        from_port = body['security_group_rule']['from_port']
        to_port = body['security_group_rule']['to_port']
       
        sec_group = self._try_create_secgroup_rule(context, credential, region_az, sec_group, from_port, to_port, cidr)
        
        return wsgi.Result(views.SecurityGroupView(sec_group, None, req, tenant_id).create(), 201)
    
    def _try_create_secgroup_rule(self, context, credential, region, secgroup, from_port, to_port, cidr):
        remote_name = 'dbaas-' + utils.generate_uuid()
        try:
            remote_rule_id = models.RemoteSecurityGroup.add_rule(credential=credential, 
                                                                 region=region, 
                                                                 secgroup_id=secgroup['remote_secgroup_id'], 
                                                                 from_port=from_port,
                                                                 to_port=to_port,
                                                                 cidr=cidr)
            
            if not remote_rule_id:
                raise exception.ReddwarfError("Failed to create Security Group Rule")
            else:
                # Create db record
                sec_group_rule = models.SecurityGroupRule.create(protocol='tcp',
                                                                 cidr=cidr,
                                                                 security_group_id=secgroup['id'],
                                                                 remote_secgroup_rule_id=remote_rule_id)
                return sec_group_rule
            
        except exception.SecurityGroupCreationFailure, e:
            LOG.exception("Failed to create remote security group")
            raise exception.ReddwarfError("Failed to create Security Group")

    def validate(self, body):
        try:
            body['security_group_rule']
            body['security_group_rule']['security_group_id']
            body['security_group_rule']['cidr']
            body['security_group_rule']['from_port']
            body['security_group_rule']['to_port']
        except KeyError as e:
            LOG.error(_("Create Security Group Rules Required field(s) - %s") % e)
            raise exception.ReddwarfError("Required element/key - %s "
                                       "was not specified" % e)