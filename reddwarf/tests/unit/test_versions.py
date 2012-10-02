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

class TestVersionController(ControllerTestBase):

    def __getitem__(self, key):
        return getattr(self, key)
    
    def setUp(self):
        super(TestVersionController, self).setUp()
        self.headers = {'X-Auth-Token': 'abc:123',
                        'X-Role': 'mysql-user',
                        'X-User-Id': '999',
                        'X-Tenant-Id': '123'}
        self.tenant = self.headers['X-Tenant-Id']
        self.versions_path = "/"
        self.version_path = "/v1.0/"      
        
    def test_index(self):
        
        response = self.app.get("%s" % (self.versions_path), headers=self.headers)
        self.assertEqual(response.status_int, 200)
        
        response_json = json.loads(response.body)
        self.assertNotEqual(len(response_json['versions']), 0, "Zero versions returned!")
    
    def test_show(self):
        
        response = self.app.get("%s" % (self.version_path), headers=self.headers)
        self.assertEqual(response.status_int, 200)
        
        response_json = json.loads(response.body)
        LOG.debug("RESPONSE JSON: %s" % response_json)
        self.assertEqual(response_json['version']['status'], "CURRENT", "Unexpected version v1.0 status returned")
        self.assertEqual(response_json['version']['links'][0]['href'], "http://localhost" + self.version_path, "Link href value is incorret")
            