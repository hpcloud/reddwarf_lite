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

import mox
import logging
import json
import novaclient.v1_1

from reddwarf import tests
from reddwarf.common import config
from reddwarf.common import utils
from reddwarf.common import wsgi
from reddwarf.database import models
from reddwarf.database import service
from reddwarf.database import views
from reddwarf.tests import unit

import unittest


LOG = logging.getLogger(__name__)


class ControllerTestBase(tests.BaseTest):

    def setUp(self):
        super(ControllerTestBase, self).setUp()
        conf, reddwarf_app = config.Config.load_paste_app('reddwarfapp',
                {"config_file": tests.test_config_file()}, None)
        self.app = unit.TestApp(reddwarf_app)


class TestInstanceController(ControllerTestBase):

    DUMMY_INSTANCE_ID = "123"
    DUMMY_INSTANCE = {"id": DUMMY_INSTANCE_ID,
    "name": "DUMMY_NAME",
    "status": "BUILD",
    "created": "createtime",
    "updated": "updatedtime",
    "hostname": "remotehost",
    "port": "12345",
    "links": [],
    "credential": "credential"}
    
    DUMMY_SERVER = {
        "uuid": utils.generate_uuid(), 
        "id": "76543",
        "name": "test_server"
    }

    def setUp(self):
        self.instances_path = "/tenant/instances"
        super(TestInstanceController, self).setUp()

    # TODO(hub-cap): Start testing the failure cases
    # def test_show_broken(self):
    #     response = self.app.get("%s/%s" % (self.instances_path,
    #                                        self.DUMMY_INSTANCE_ID),
    #                                        headers={'X-Auth-Token': '123'})
    #     self.assertEqual(response.status_int, 404)

    def test_show(self):
        id = self.DUMMY_INSTANCE_ID
        self.mock.StubOutWithMock(models.DBInstance, 'find_by')
        models.DBInstance.find_by(id=id).AndReturn(self.DUMMY_INSTANCE)
#        self.mock.StubOutWithMock(models.DBInstance, '__init__')
#        models.Instance.__init__(context=mox.IgnoreArg(), uuid=mox.IgnoreArg())
        self.mock.ReplayAll()

        response = self.app.get("%s/%s" % (self.instances_path,
                                           self.DUMMY_INSTANCE_ID),
                                           headers={'X-Auth-Token': '123'})

        self.assertEqual(response.status_int, 200)

    def test_index(self):
        self.mock.StubOutWithMock(models.DBInstance, 'list')
        models.DBInstance.list().AndReturn([self.DUMMY_INSTANCE])
        self.mock.ReplayAll()
        response = self.app.get("%s" % (self.instances_path),
                                           headers={'X-Auth-Token': '123'})
        self.assertEqual(response.status_int, 200)

    def mock_out_client_create(self):
        """Stubs out a fake server returned from novaclient.
           This is akin to calling Client.servers.get(uuid)
           and getting the server object back."""
        self.FAKE_SERVER = self.mock.CreateMock(object)
        self.FAKE_SERVER.name = 'my_name'
        self.FAKE_SERVER.status = 'ACTIVE'
        self.FAKE_SERVER.updated = utils.utcnow()
        self.FAKE_SERVER.created = utils.utcnow()
        self.FAKE_SERVER.id = utils.generate_uuid()
        self.FAKE_SERVER.flavor = 'http://localhost/1234/flavors/1234'
        self.FAKE_SERVER.links = [{
                    "href": "http://localhost/1234/instances/123",
                    "rel": "self"
                },
                {
                    "href": "http://localhost/1234/instances/123",
                    "rel": "bookmark"
                }]
        self.FAKE_SERVER.addresses = {
                "private": [
                    {
                        "addr": "10.0.0.4",
                        "version": 4
                    }
                ]
            }

        client = self.mock.CreateMock(novaclient.v1_1.Client)
        servers = self.mock.CreateMock(novaclient.v1_1.servers.ServerManager)
        servers.create(mox.IgnoreArg(),
                       mox.IgnoreArg(),
                       mox.IgnoreArg()).AndReturn(self.FAKE_SERVER)
        client.servers = servers
        self.mock.StubOutWithMock(models.RemoteModelBase, 'get_client')
        models.RemoteModelBase.get_client(mox.IgnoreArg()).AndReturn(client)

    def test_create(self):
        self.ServiceImage = {"image_id": "1240"}
        self.ServiceFlavor = {"flavor_id": "100"}
        body = {
            "instance": {
                "databases": [
                    {
                        "character_set": "utf8",
                        "collate": "utf8_general_ci",
                        "name": "sampledb"
                    },
                    {
                        "name": "nextround"
                    }
                ],
                "flavorRef": "http://localhost/v0.1/tenant/flavors/1",
                "name": "json_rack_instance",
            }
        }
        
        self.mock.StubOutWithMock(models.ServiceImage, 'find_by')
        models.ServiceImage.find_by(service_name="database").AndReturn(self.ServiceImage)
        self.mock.StubOutWithMock(models.ServiceFlavor, 'find_by')
        models.ServiceFlavor.find_by(service_name="database").AndReturn(self.ServiceFlavor)                
        
        mock_server = self.mock.CreateMock(models.Instance(server="server", uuid=utils.generate_uuid()))
        self.mock.StubOutWithMock(service.InstanceController, '_try_create_server')
        service.InstanceController._try_create_server(mox.IgnoreArg(),
                            mox.IgnoreArg(), mox.IgnoreArg(), mox.IgnoreArg()).AndReturn(mock_server)
        
        self.mock.StubOutWithMock(mock_server, 'data')
        mock_server.data().AndReturn(self.DUMMY_SERVER)       
        
        self.mock.StubOutWithMock(models.DBInstance, 'create')
        models.DBInstance.create(address='ip', port='3306', flavor=1,
                name=body['instance']['name'],
                status='building',
                remote_id=self.DUMMY_SERVER['id'],
                remote_uuid=self.DUMMY_SERVER['uuid'],
                remote_hostname=self.DUMMY_SERVER['name'],
                user_id=None,
                tenant_id='tenant').AndReturn(models.DBInstance())  

        self.mock.StubOutWithMock(models.DBInstance, 'data')
        models.DBInstance.data().AndReturn(self.DUMMY_INSTANCE)
                 
        #self.mock_out_client_create()
        self.mock.ReplayAll()

        response = self.app.post_json("%s" % (self.instances_path), body=body,
                                           headers={'X-Auth-Token': '123'},
                                           )
        self.assertEqual(response.status_int, 201)


