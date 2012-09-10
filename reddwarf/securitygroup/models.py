# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 Hewlett-Packard Development Company, L.P.
# Copyright 2010-2011 OpenStack LLC.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http: //www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""Model classes that form the core of instances functionality."""

import logging
import netaddr

from reddwarf import db

from reddwarf.common import config
from reddwarf.common import exception as rd_exceptions
from reddwarf.common import utils

from reddwarf.database.models import DatabaseModelBase
from reddwarf.database.models import RemoteModelBase

from novaclient import exceptions as nova_exceptions

CONFIG = config.Config
LOG = logging.getLogger(__name__)






class RemoteSecurityGroup(RemoteModelBase):

    _data_fields = ['id', 'name', 'description', 'rules']
    
    def __init__(self, security_group=None, credential=None, region=None, id=None):
        if id is None and security_group is None:
            msg = "id is not defined"
            raise rd_exceptions.InvalidModelError(msg)
        elif security_group is None:
            try:
                self._data_object = self.get_client(credential, region).security_groups.get(id)
            except nova_exceptions.NotFound, e:
                raise rd_exceptions.NotFound(id=id)
            except nova_exceptions.ClientException, e:
                raise rd_exceptions.ReddwarfError(str(e))
        else:
            self._data_object = security_group

    @classmethod
    def create(cls, credential, region, name, description):
        """Creates a new Volume"""
        client = cls.get_client(credential, region)
        
        try:
            secgroup = client.security_groups.create(name=name, description=description)
        except nova_exceptions.ClientException, e:
            LOG.exception('Failed to create remote security group')
            raise rd_exceptions.SecurityGroupCreationFailure(str(e))

        return RemoteSecurityGroup(security_group=secgroup)
    
    @classmethod
    def delete(cls, credential, region, secgroup_id):
        client = cls.get_client(credential, region)
        
        try:
            client.security_groups.delete(secgroup_id)
        except nova_exceptions.ClientException, e:
            LOG.exception('Failed to delete remote security group')
            raise rd_exceptions.SecurityGroupRuleDeletionFailure(str(e))

    @classmethod
    def add_rule(cls, credential, region, secgroup_id, from_port, to_port, cidr):
        client = cls.get_client(credential, region)
        
        try:
            secgroup_rule = client.security_group_rules.create(parent_group_id=secgroup_id,
                                                               ip_protocol='tcp',
                                                               from_port=from_port,
                                                               to_port=to_port,
                                                               cidr=cidr)
            
            return secgroup_rule.id
        except nova_exceptions.ClientException, e:
            LOG.exception('Failed to add rule to remote security group')
            raise rd_exceptions.SecurityGroupRuleCreationFailure(str(e))
     
    @classmethod
    def delete_rule(cls, credential, region, secgroup_rule_id):
        client = cls.get_client(credential, region)
        
        try:
            client.security_group_rules.delete(secgroup_rule_id)
            
        except nova_exceptions.ClientException, e:
            LOG.exception('Failed to delete rule to remote security group')
            raise rd_exceptions.SecurityGroupDeletionFailure(str(e))   
        
        
        
class SecurityGroup(DatabaseModelBase):
    _data_fields = ['name', 'description', 'user_id', 'tenant_id']

class SecurityGroupRule(DatabaseModelBase):
    _data_fields = ['protocol', 'cidr', 'from_port', 'to_port', 'security_group_id']

class SecurityGroupInstanceAssociation(DatabaseModelBase):
    _data_fields = ['security_group_id', 'instance_id']
       
def persisted_models():
    return {
        'security_group': SecurityGroup,
        'security_group_rule': SecurityGroupRule,
        'security_group_instance_association': SecurityGroupInstanceAssociation
    }
