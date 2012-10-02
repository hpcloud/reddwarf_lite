# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 Hewlett-Packard Development Company, L.P.
#
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

import mox
import logging
import json
import novaclient.v1_1

from reddwarf import tests
from reddwarf import db
from reddwarf.common import config
from reddwarf.common import utils
from reddwarf.common import wsgi
from reddwarf.securitygroup import models
from reddwarf.securitygroup import service
from reddwarf.securitygroup import views

from reddwarf.database import models as instance_models

from reddwarf.db.sqlalchemy import api
from reddwarf.tests import unit

import unittest


LOG = logging.getLogger(__name__)


class ControllerTestBase(tests.BaseTest):

    def setUp(self):
        super(ControllerTestBase, self).setUp()
        conf, reddwarf_app = config.Config.load_paste_app('reddwarf',
                {"config_file": tests.test_config_file()}, None)
        self.app = unit.TestApp(reddwarf_app)

class DummyQueryResult():
            
    def __getitem__(self, key):
        return getattr(self, key)

class TestSecurityGroupController(ControllerTestBase):

    DUMMY_SECGROUP_ID = "123456789"
    
    DUMMY_SECGROUP = {
        "id": DUMMY_SECGROUP_ID, 
        "name": "test_secgroup",
        "description": "test",
        "remote_secgroup_id": "9999",
        "remote_secgroup_name": "remote name",
        "created_at": "now",
        "updated_at": "now2"
    }

    DUMMY_SECGROUP_RULES = [{
        "id": "1111",
        "protocol": "tcp",
        "cidr": "0.0.0.0/0",
        "from_port": 3306,
        "to_port": 3306,
        "security_group_id": DUMMY_SECGROUP_ID,
        "remote_secgroup_rule_id": "3333" 
    }]

    def setUp(self):
        super(TestSecurityGroupController, self).setUp()
        self.headers = {'X-Auth-Token': 'abc:123',
                        'X-Role': 'mysql-user',
                        'X-User-Id': '999',
                        'X-Tenant-Id': '123'}
        self.tenant = self.headers['X-Tenant-Id']
        self.secgroups_path = "/v1.0/" + self.tenant + "/security-groups"


    def test_index(self):
        
        self.mock.StubOutWithMock(models.SecurityGroup, 'find_all')
        sec_groups = models.SecurityGroup().find_all(tenant_id=self.tenant, deleted=False).AndReturn([self.DUMMY_SECGROUP])

        self.mock.StubOutWithMock(models.SecurityGroupRule, 'find_all')
        sec_groups = models.SecurityGroupRule().find_all(security_group_id=self.DUMMY_SECGROUP_ID, deleted=False).AndReturn(self.DUMMY_SECGROUP_RULES)

        self.mock.ReplayAll()

        response = self.app.get("%s" % (self.secgroups_path), headers=self.headers)
        self.assertEqual(response.status_int, 200)
        
        self.assertNotEquals(response.body, None, "Reponse body to SecurityGroups - show() should not be None")
        
        response_json = json.loads(response.body)
        self.assertEqual(len(response_json['security_groups']), 1, 'Unexpected security_groups length in Response')


    def test_show(self):
        id = self.DUMMY_SECGROUP_ID
        #respone
        
        self.mock.StubOutWithMock(models.SecurityGroup, 'find_by')
        sec_group = models.SecurityGroup().find_by(id=id, tenant_id=self.tenant, deleted=False).AndReturn(self.DUMMY_SECGROUP)
        
        self.mock.StubOutWithMock(models.SecurityGroupRule, 'find_all')
        group_rules = models.SecurityGroupRule().find_all(deleted=False, security_group_id=id).AndReturn(self.DUMMY_SECGROUP_RULES)
        
        self.mock.ReplayAll()

        response = self.app.get("%s/%s" % (self.secgroups_path,
                                           self.DUMMY_SECGROUP_ID),
                                           headers=self.headers)


        self.assertEqual(response.status_int, 200)
        
        self.assertNotEquals(response.body, None, "Reponse body to SecurityGroups - show() should not be None")
        
        response_json = json.loads(response.body)
        self.assertEqual(response_json['security_group']['name'], 'test_secgroup', 'Unexpected security_group name in Response')
        self.assertEqual(response_json['security_group']['id'], self.DUMMY_SECGROUP_ID, 'Unexpected security_group id in Response')
        self.assertEqual(len(response_json['security_group']['rules']), 1, 'Unexpected security_group rule length in Response')
        


class TestSecurityGroupRuleController(ControllerTestBase):

    DUMMY_SECGROUP_ID = "123456789"
    DUMMY_SECGROUP_RULE_ID = "123456789123456789"
    
    DUMMY_SECGROUP = {
        "id": DUMMY_SECGROUP_ID, 
        "name": "test_secgroup",
        "description": "test",
        "remote_secgroup_id": "9999",
        "remote_secgroup_name": "remote name",
        "credential": "1",
        "availability_zone": "az2",
        "created_at": "now",
        "updated_at": "now2"
    }
    
    DUMMY_SECGROUP_RULE = {
        "id": DUMMY_SECGROUP_RULE_ID, 
        "protocol": "tcp",
        "cidr": "0.0.0.0/0",
        "security_group_id": DUMMY_SECGROUP_ID,
        "remote_secgroup_rule_id": "8888",
        "created_at": "now",
        "updated_at": "now2"
    }



    def setUp(self):
        super(TestSecurityGroupRuleController, self).setUp()
        self.headers = {'X-Auth-Token': 'abc:123',
                        'X-Role': 'mysql-user',
                        'X-User-Id': '999',
                        'X-Tenant-Id': '123'}
        self.tenant = self.headers['X-Tenant-Id']
        self.secgroup_rules_path = "/v1.0/" + self.tenant + "/security-group-rules"
        
    def test_create(self):
        body = {
            "security_group_rule" : {
                "cidr": "0.0.0.0/0",
                "from_port": 3306,
                "to_port": 3306,
                "security_group_id": self.DUMMY_SECGROUP_ID
            } 
        }
        
        self.mock.StubOutWithMock(models.SecurityGroup, 'find_by')
        sec_group = models.SecurityGroup().find_by(id=self.DUMMY_SECGROUP_ID, 
                                                   tenant_id=self.tenant, 
                                                   deleted=False).AndReturn(self.DUMMY_SECGROUP)

        self.mock.StubOutWithMock(instance_models.Credential, 'find_by')
        credential = instance_models.Credential().find_by(id=sec_group['credential']).AndReturn(None)
        
        self.mock.StubOutWithMock(models.RemoteSecurityGroup, 'add_rule')
        models.RemoteSecurityGroup.add_rule(cidr=body['security_group_rule']['cidr'], 
                                            credential=credential, 
                                            from_port=body['security_group_rule']['from_port'],
                                            to_port=body['security_group_rule']['to_port'],
                                            region='az2',
                                            secgroup_id=self.DUMMY_SECGROUP['remote_secgroup_id']).AndReturn(55555)
        
        self.mock.ReplayAll()

        response = self.app.post_json("%s" % (self.secgroup_rules_path), body=body,
                                           headers=self.headers,
                                           )


        self.assertEqual(response.status_int, 201)
        
        self.assertNotEquals(response.body, None, "Reponse body to SecurityGroupRules - create() should not be None")
        
        response_json = json.loads(response.body)
        self.assertEqual(response_json['security_group_rule']['from_port'], 3306, 'Unexpected security_group name in Response')
        self.assertEqual(response_json['security_group_rule']['to_port'], 3306, 'Unexpected security_group id in Response')

    def test_delete(self):
        
        rule = models.SecurityGroupRule()
        rule.merge_attributes(self.DUMMY_SECGROUP_RULE)
        
        self.mock.StubOutWithMock(models.SecurityGroupRule, 'find_by')
        sec_group_rule = models.SecurityGroupRule().find_by(id=self.DUMMY_SECGROUP_RULE_ID, 
                                                            deleted=False).AndReturn(rule)

        self.mock.StubOutWithMock(models.SecurityGroup, 'find_by')
        sec_group = models.SecurityGroup().find_by(id=sec_group_rule['security_group_id'], 
                                                   tenant_id=self.tenant, 
                                                   deleted=False).AndReturn(self.DUMMY_SECGROUP)
                                                   
        self.mock.StubOutWithMock(instance_models.Credential, 'find_by')
        credential = instance_models.Credential().find_by(id=sec_group['credential']).AndReturn(None)
        
        self.mock.StubOutWithMock(models.RemoteSecurityGroup, 'delete_rule')
        models.RemoteSecurityGroup.delete_rule(credential, 
                                               'az2',
                                               sec_group_rule['remote_secgroup_rule_id']).AndReturn(None)

        self.mock.StubOutWithMock(models.SecurityGroupRule, 'delete')
        models.SecurityGroupRule().delete()
    
        self.mock.ReplayAll()

        response = self.app.delete(("%s/%s" % (self.secgroup_rules_path, sec_group_rule['id'])), headers=self.headers)
        
        self.assertEqual(response.status_int, 204)
