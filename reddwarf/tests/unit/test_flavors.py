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

from reddwarf import tests
from reddwarf.common import config
from reddwarf.common import utils
from reddwarf.common import wsgi
from reddwarf.database import models

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

class TestFlavorController(ControllerTestBase):
    
    FLAVOR_ID = 101
    
    DUMMY_FLAVOR = {
        "vcpus" : 1,
        "ram" : 1,
        "id" : 1,
        "flavor_id" : FLAVOR_ID,
        "deleted" : 0,
        "flavor_name" : "xsmall",
        "service_name": "database"
    }

    def __getitem__(self, key):
        return getattr(self, key)
    
    def setUp(self):
        super(TestFlavorController, self).setUp()
        self.headers = {'X-Auth-Token': 'abc:123',
                        'X-Role': 'mysql-user',
                        'X-User-Id': '999',
                        'X-Tenant-Id': '123'}
        self.tenant = self.headers['X-Tenant-Id']
        self.flavors_path = "/v1.0/" + self.tenant + "/flavors"      
        
    def test_index(self):
        self.mock.StubOutWithMock(models.ServiceFlavor, 'find_all')
        flavors = models.ServiceFlavor().find_all().AndReturn([self.DUMMY_FLAVOR])
        
        self.mock.ReplayAll()
        
        response = self.app.get("%s" % (self.flavors_path), headers=self.headers)
        self.assertEqual(response.status_int, 200)
        
        response_json = json.loads(response.body)
        self.assertEqual(len(response_json['flavors']), 1, "Unexpected number of flavors returned")
    
    def test_index_detail(self):
        self.mock.StubOutWithMock(models.ServiceFlavor, 'find_all')
        flavors = models.ServiceFlavor().find_all().AndReturn([self.DUMMY_FLAVOR])
        
        self.mock.ReplayAll()
        
        response = self.app.get("%s" % (self.flavors_path + "/detail"), headers=self.headers)
        self.assertEqual(response.status_int, 200)
        
        response_json = json.loads(response.body)
        self.assertEqual(len(response_json['flavors']), 1, "Unexpected number of flavors returned")
    
    def test_show(self):
        self.mock.StubOutWithMock(models.ServiceFlavor, 'find_by')
        flavors = models.ServiceFlavor().find_by(flavor_id=self.FLAVOR_ID).AndReturn(self.DUMMY_FLAVOR)
        
        self.mock.ReplayAll()
        
        response = self.app.get("%s" % (self.flavors_path + "/" + str(self.FLAVOR_ID)), headers=self.headers)
        self.assertEqual(response.status_int, 200)
        
        response_json = json.loads(response.body)
        self.assertEqual(response_json['flavor']['name'], "xsmall", "Unexpected flavor name returned")
        self.assertEqual(response_json['flavor']['id'], self.FLAVOR_ID, "Unexpected id returned")
        self.assertEqual(response_json['flavor']['links'][0]['href'], "http://localhost" + self.flavors_path + "/" + str(self.FLAVOR_ID), "Link href value is incorret")
            