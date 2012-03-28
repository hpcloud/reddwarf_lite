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
import novaclient.v1_1

from reddwarf import tests
from reddwarf.common import exception
from reddwarf.common import utils
from reddwarf.database import models
from reddwarf.db import db_query
from reddwarf.tests import unit
from reddwarf.tests.factories import models as factory_models


class TestInstance(tests.BaseTest):

    FAKE_SERVER = None

    def setUp(self):
        super(TestInstance, self).setUp()

    def mock_out_client(self):
        """Stubs out a fake server returned from novaclient.
           This is akin to calling Client.servers.get(uuid)
           and getting the server object back."""
        self.FAKE_SERVER = self.mock.CreateMock(object)
        self.FAKE_SERVER.name = 'my_name'
        self.FAKE_SERVER.status = 'ACTIVE'
        self.FAKE_SERVER.updated = utils.utcnow()
        self.FAKE_SERVER.created = utils.utcnow()
        self.FAKE_SERVER.id = utils.generate_uuid()
        self.FAKE_SERVER.uuid = self.FAKE_SERVER.id
        self.FAKE_SERVER.flavor = ('http://localhost/1234/flavors/',
                                   '52415800-8b69-11e0-9b19-734f1195ff37')
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
        servers.get(mox.IgnoreArg()).AndReturn(self.FAKE_SERVER)
        client.servers = servers
        self.mock.StubOutWithMock(models.RemoteModelBase, 'get_client')
        models.RemoteModelBase.get_client(mox.IgnoreArg()).AndReturn(client)
        self.mock.ReplayAll()

    def test_create_instance_data(self):
        """This ensures the data() call in a new
           Instance object returns the proper mapped data
           to a dict from attr's"""
        self.mock_out_client()
        # Creates the instance via __init__
        instance = factory_models.Instance().data()

        self.assertEqual(instance['name'], self.FAKE_SERVER.name)
        self.assertEqual(instance['status'], self.FAKE_SERVER.status)
        self.assertEqual(instance['updated'], self.FAKE_SERVER.updated)
        self.assertEqual(instance['created'], self.FAKE_SERVER.created)
        self.assertEqual(instance['id'], self.FAKE_SERVER.id)
        self.assertEqual(instance['uuid'], self.FAKE_SERVER.uuid)        
        self.assertEqual(instance['flavor'], self.FAKE_SERVER.flavor)
        self.assertEqual(instance['links'], self.FAKE_SERVER.links)
        self.assertEqual(instance['addresses'], self.FAKE_SERVER.addresses)
        
class TestDBInstance(tests.BaseTest):
    
    FAKE_SERVER = None
    
    def setUp(self):
        super(TestDBInstance, self).setUp()              
    
    def test_create_instance(self):
        remote_uuid = utils.generate_uuid()
        kwargs = {"remote_uuid": remote_uuid,
                  "name": "dbapi_test"}
        instance = factory_models.DBInstance().create(**kwargs).data()
        
        self.assertEqual(instance['name'], "dbapi_test")
        self.assertEqual(instance['deleted'], False)
        self.assertNotEqual(instance['created_at'], None)
        self.assertEqual(len(instance['id']), len(utils.generate_uuid()))
        self.assertEqual(instance['remote_uuid'], remote_uuid)
    
    def test_delete_instance(self):
        kwargs = {}
        instance = factory_models.DBInstance().create(**kwargs)
        data = instance.data()
        self.assertEqual(data['deleted'], False)
        self.assertEqual(data['deleted_at'], None)
        
        data = instance.delete(**kwargs).data()
        self.assertEqual(data['deleted'], True)
        self.assertNotEqual(data['deleted_at'], None)              
         
    def test_update_instance(self):
        kwargs = {"name": "dbapi_test"}
        instance = factory_models.DBInstance().create(**kwargs)        
        data = instance.data()
        self.assertEqual(data['name'], "dbapi_test")
        
        kwargs['name'] = "changed"
        data = instance.update(**kwargs).data()
        self.assertEqual(data['name'], "changed")
    
    def test_retrieve_instance(self):
        name = utils.generate_uuid()
        kwargs = {"name": name}
        instance = factory_models.DBInstance().create(**kwargs)
        data = instance.data()
        self.assertEqual(data['name'], name)
 
        found_instance = instance.find_by(name=name)
        data = found_instance.data()
        self.assertEqual(data['name'], name)
    
class TestSnapshotInstance(tests.BaseTest):
    
    def setUp(self):
        super(TestSnapshotInstance, self).setUp() 

    def test_create_snapshot(self):
        kwargs = {}
        instance = factory_models.Snapshot().create(**kwargs).data()
        
        print instance
        
        self.assertEqual(instance['deleted'], False)
        self.assertNotEqual(instance['created_at'], None)
        self.assertEqual(len(instance['id']), len(utils.generate_uuid()))
    
    def test_delete_snapshot(self):
        kwargs = {}
        snapshot = factory_models.Snapshot().create(**kwargs)
        data = snapshot.data()
        self.assertEqual(data['deleted'], False)
        self.assertEqual(data['deleted_at'], None)
        
        data = snapshot.delete(**kwargs).data()
        self.assertEqual(data['deleted'], True)
        self.assertNotEqual(data['deleted_at'], None) 
    
    def test_update_snapshot(self):
        kwargs = {"name": "dbapi_test"}
        snapshot = factory_models.Snapshot().create(**kwargs)        
        data = snapshot.data()
        self.assertEqual(data['name'], "dbapi_test")
        
        kwargs['name'] = "changed"
        data = snapshot.update(**kwargs).data()
        self.assertEqual(data['name'], "changed")
    
    def test_retrieve_snapshot(self):
        name = utils.generate_uuid()
        kwargs = {"name": name}
        snapshot = factory_models.Snapshot().create(**kwargs)
        data = snapshot.data()
        self.assertEqual(data['name'], name)
 
        found_snapshot = snapshot.find_by(name=name)
        data = found_snapshot.data()
        self.assertEqual(data['name'], name)
