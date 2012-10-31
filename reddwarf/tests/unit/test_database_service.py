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
from reddwarf.database import models
from reddwarf.database import service
from reddwarf.database import views
from reddwarf.database import worker_api
from reddwarf.database import guest_api
from reddwarf.securitygroup import models as secgroup_models
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

class TestInstanceController(ControllerTestBase):

    DUMMY_INSTANCE_ID = "12345678-1234-1234-1234-123456789abc"
    DUMMY_INSTANCE = {"id": DUMMY_INSTANCE_ID,
    "name": "DUMMY_NAME",
    "status": "BUILD",
    "created_at": "createtime",
    "updated_at": "updatedtime",
    "remote_hostname": "remotehost",
    "flavor": "4",
    "port": "12345",
    "links": [],
    "credential": "credential",
    "address" : "ipaddress"}
    
    DUMMY_GUEST_STATUS = DummyQueryResult ()
    DUMMY_GUEST_STATUS.id = '87654321-1234-1234-1234-123456789abc'
    DUMMY_GUEST_STATUS.instance_id = '12345678-1234-1234-1234-123456789abc'
    DUMMY_GUEST_STATUS.state = 'BUILDING'
    
    DUMMY_SERVER = {
        "uuid": utils.generate_uuid(), 
        "id": "76543",
        "name": "test_server",
        "remote_id": 22222,
        "flavor": "4",
        "credential": "credential",
        "address" : "ipaddress" ,
        "created_at": "createtime",
        "updated_at": "updatedtime"
    }

    DUMMY_FLOATING_IP = "10.10.10.10"

    def setUp(self):
        super(TestInstanceController, self).setUp()
        self.headers = {'X-Auth-Token': 'abc:123',
                        'X-Role': 'mysql-user',
                        'X-User-Id': '999',
                        'X-Tenant-Id': '123'}
        self.tenant = self.headers['X-Tenant-Id']
        self.instances_path = "/v1.0/" + self.tenant + "/instances"
        

    # TODO(hub-cap): Start testing the failure cases
    # def test_show_broken(self):
    #     response = self.app.get("%s/%s" % (self.instances_path,
    #                                        self.DUMMY_INSTANCE_ID),
    #                                        headers={'X-Auth-Token': '123'})
    #     self.assertEqual(response.status_int, 404)

    def test_show(self):
        id = self.DUMMY_INSTANCE_ID
        flavor = self.DUMMY_INSTANCE['flavor']
        self.mock.StubOutWithMock(models.DBInstance, 'find_by')
        models.DBInstance.find_by(deleted=False,id=id,tenant_id=self.tenant).AndReturn(self.DUMMY_INSTANCE)
#        self.mock.StubOutWithMock(models.DBInstance, '__init__')
#        models.Instance.__init__(context=mox.IgnoreArg(), uuid=mox.IgnoreArg())

        self.mock.StubOutWithMock(models.GuestStatus, 'find_by')
        models.GuestStatus.find_by(deleted=False,instance_id=id).AndReturn({'instance_id': id, 'state': 'running'})

        self.mock.StubOutWithMock(models.ServiceFlavor, 'find_by')
        models.ServiceFlavor.find_by(deleted=False, id=flavor).AndReturn({'id': '4', 'flavor_id': '104'})

        self.mock.StubOutWithMock(secgroup_models.SecurityGroupInstances, 'find_by')
        secgroup_models.SecurityGroupInstances.find_by(instance_id=id, deleted=False).AndReturn({'security_group_id': '123'})
        
        self.mock.StubOutWithMock(secgroup_models.SecurityGroup, 'find_by')
        secgroup_models.SecurityGroup.find_by(id='123', deleted=False).AndReturn({'id': '234'})
        
        self.mock.ReplayAll()

        response = self.app.get("%s/%s" % (self.instances_path,
                                           self.DUMMY_INSTANCE_ID),
                                           headers=self.headers)


        self.assertEqual(response.status_int, 200)
        self.mock.UnsetStubs()

    def test_index(self):
        flavor = self.DUMMY_INSTANCE['flavor']
        self.mock.StubOutWithMock(models.DBInstance, 'find_all')
        models.DBInstance.find_all(tenant_id=self.tenant, deleted=False).AndReturn([self.DUMMY_INSTANCE])

        self.mock.StubOutWithMock(models.ServiceFlavor, 'find_all')
        models.ServiceFlavor.find_all().AndReturn([{'id': '1', 'flavor_id': '101'},
                                                  {'id': '2', 'flavor_id': '102'},
                                                  {'id': '3', 'flavor_id': '103'},
                                                  {'id': '4', 'flavor_id': '104'},
                                                  {'id': '5', 'flavor_id': '105'}])
        
        self.mock.StubOutWithMock(api, 'find_guest_statuses_for_instances')
        api.find_guest_statuses_for_instances([self.DUMMY_INSTANCE_ID]).AndReturn([self.DUMMY_GUEST_STATUS])
        
        self.mock.ReplayAll()
        
        response = self.app.get("%s" % (self.instances_path),
                                        headers=self.headers)
        
        self.assertEqual(response.status_int, 200)
        self.mock.UnsetStubs()

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
        self.ServiceFlavor = {"id": "1", "flavor_id": "100"}
        self.ServiceKeypair = {"key_name": "dbas-dev"}
        self.ServiceZone = {"availability_zone": "az2"}
        self.Credential = {'id': '1'}
        body = {
            "instance": {
                "name": "json_rack_instance",
                "flavorRef": "104"
            }
        }
        flavor = self.DUMMY_SERVER['flavor']
        
        mock_flip_data = {"ip": "blah"}
        
        default_quotas = [{ "tenant_id": self.tenant, "hard_limit": 3, "resource":"instances"},
                          { "tenant_id": self.tenant, "hard_limit": 10, "resource":"snapshots"},
                          { "tenant_id": self.tenant, "hard_limit": 20, "resource":"volume_space"}]
        
        default_secgroup_api_response = { 'security_group' : { 'id' : '123' } }
        dummy_db_secgroup = { 'id': '123', 'remote_secgroup_name': 'test' }
        
        self.mock.StubOutWithMock(models.Quota, 'find_all')
        models.Quota.find_all(tenant_id=self.tenant, deleted=False).AndReturn(default_quotas)
        models.Quota.find_all(tenant_id=self.tenant, deleted=False).AndReturn(default_quotas)

        self.mock.StubOutWithMock(models.ServiceZone, 'find_by')
        models.ServiceZone.find_by(service_name="database", tenant_id='123', deleted=False).AndReturn(self.ServiceZone)  
        self.mock.StubOutWithMock(models.ServiceImage, 'find_by')
        models.ServiceImage.find_by(service_name="database", tenant_id='123', availability_zone=self.ServiceZone["availability_zone"], deleted=False).AndReturn(self.ServiceImage)
        self.mock.StubOutWithMock(models.ServiceFlavor, 'find_by')
        models.ServiceFlavor.find_by(service_name="database", flavor_id='104', deleted=False).AndReturn(self.ServiceFlavor)
        self.mock.StubOutWithMock(models.ServiceKeypair, 'find_by')
        models.ServiceKeypair.find_by(service_name="database", deleted=False).AndReturn(self.ServiceKeypair)  
        self.mock.StubOutWithMock(models.Credential, 'find_by')
        models.Credential.find_by(type="compute", deleted=False).AndReturn(self.Credential)                
        
        mock_server = self.mock.CreateMock(models.Instance(server="server", uuid=utils.generate_uuid()))
        #mock_dbinstance = self.mock.CreateMock(models.DBInstance())
        mock_dbinstance = {'id': 'id', 'name': 'name', 'created_at': 'created_at', 'address': 'address'}
#        mock_flip = self.mock.CreateMock(models.FloatingIP(floating_ip="flip", id=123))       

        self.mock.StubOutWithMock(service.InstanceController, '_try_create_security_group')
        service.InstanceController._try_create_security_group(mox.IgnoreArg(), mox.IgnoreArg(),
                                                              mox.IgnoreArg(), mox.IgnoreArg()).AndReturn(default_secgroup_api_response)

        self.mock.StubOutWithMock(secgroup_models.SecurityGroup, 'find_by')
        secgroup_models.SecurityGroup.find_by(id='123', deleted=False).AndReturn(dummy_db_secgroup)                

        self.mock.StubOutWithMock(service.InstanceController, '_try_create_server')
        
        service.InstanceController._try_create_server(mox.IgnoreArg(), mox.IgnoreArg(),
                            mox.IgnoreArg(), mox.IgnoreArg(), mox.IgnoreArg(), mox.IgnoreArg(), mox.IgnoreArg(), 
                            mox.IgnoreArg(), mox.IgnoreArg(), mox.IgnoreArg()).AndReturn((self.DUMMY_SERVER, self.DUMMY_GUEST_STATUS, {'/home/nova/agent.config':'blah'}))

        self.mock.StubOutWithMock(service.InstanceController, '_try_assign_floating_ip')
        service.InstanceController._try_assign_floating_ip(mox.IgnoreArg(), mox.IgnoreArg(), mox.IgnoreArg()).AddReturn(self.DUMMY_FLOATING_IP)

        self.mock.StubOutWithMock(service.InstanceController, '_try_attach_volume')
        
        service.InstanceController._try_attach_volume(mox.IgnoreArg(),
                            mox.IgnoreArg(), mox.IgnoreArg(), mox.IgnoreArg(), mox.IgnoreArg(), mox.IgnoreArg()).AndReturn(None)
        
        #volume = models.Volume.create(credential, region, volume_size, 'mysql-%s' % instance['remote_id']).data()
        
        self.mock.StubOutWithMock(worker_api.API, 'ensure_create_instance')
        worker_api.API.ensure_create_instance(mox.IgnoreArg(), mox.IgnoreArg(), mox.IgnoreArg()).AndReturn(None)

        #self.mock_out_client_create()
        self.mock.ReplayAll()

        response = self.app.post_json("%s" % (self.instances_path), body=body,
                                           headers=self.headers,
                                           )
        self.assertEqual(response.status_int, 201)
        self.mock.UnsetStubs()

    def test_floating_ip_assignment(self):
        service.InstanceController._try_assign_floating_ip(mox.IgnoreArg(), mox.IgnoreArg(), mox.IgnoreArg()).AddReturn(self.DEFAULT)

    def test_create_quota_error(self):
        
        body = {
            "instance": {
                "name": "json_rack_instance",
            }
        }

        default_quotas = [{ "tenant_id": self.tenant, "hard_limit": 0, "resource":"instances"},
                          { "tenant_id": self.tenant, "hard_limit": 10, "resource":"snapshots"}]
        
        self.mock.StubOutWithMock(models.Quota, 'find_all')
        models.Quota.find_all(tenant_id=self.tenant, deleted=False).AndReturn(default_quotas)
        models.Quota.find_all(tenant_id=self.tenant, deleted=False).AndReturn(default_quotas)
        
        self.mock.ReplayAll()

        # Expect an error to come back, so this doesn't throw
        response = self.app.post_json("%s" % (self.instances_path), body=body,
                                           headers=self.headers, expect_errors=True
                                           )
        
        self.assertEqual(response.status_int, 413)
        self.mock.UnsetStubs()        

class TestSnapshotController(ControllerTestBase):

    DUMMY_SNAPSHOT_ID = "87654321-1234-1234-1234-123456789abc"
    DUMMY_INSTANCE_ID = "12345678-1234-1234-1234-123456789abc"
    DUMMY_SNAPSHOT = {"id": DUMMY_SNAPSHOT_ID,
    "name": "DUMMY_NAME",
    "instance_id": DUMMY_INSTANCE_ID,
    "state": "success",
    "created_at": "createtime",
    "updated_at": "updatedtime",
    "deleted_at": None,
    "links": [] }
    
    def setUp(self):
        super(TestSnapshotController, self).setUp()
        self.headers = {'X-Auth-Token': 'abc:123',
                        'X-Role': 'mysql-user',
                        'X-User-Id': '999',
                        'X-Tenant-Id': '123'}
        self.tenant = self.headers['X-Tenant-Id']
        self.snapshots_path = "/v1.0/" + self.tenant + "/snapshots"

    def test_show(self):
        id = self.DUMMY_SNAPSHOT_ID

        self.mock.StubOutWithMock(models.Snapshot, 'find_by')
        models.Snapshot.find_by(deleted=False,id=id).AndReturn(self.DUMMY_SNAPSHOT)

        self.mock.ReplayAll()

        response = self.app.get("%s/%s" % (self.snapshots_path,
                                           self.DUMMY_SNAPSHOT_ID),
                                           headers=self.headers)

        self.assertEqual(response.status_int, 200)

    def test_index(self):
        self.mock.StubOutWithMock(models.Snapshot, 'list_by_tenant')
        models.Snapshot.list_by_tenant(self.tenant).AndReturn([self.DUMMY_SNAPSHOT])

        self.mock.ReplayAll()
        
        response = self.app.get("%s" % (self.snapshots_path),
                                        headers=self.headers)
        
        self.assertEqual(response.status_int, 200)
        
    
    def test_create(self):

        body = {
            "snapshot": {
                "name": "snapshot unit test",
                "instanceId" : self.DUMMY_INSTANCE_ID
            }
        }
        
        # Ensure we give back a 'running' instance
        self.mock.StubOutWithMock(models.GuestStatus, 'find_by')
        models.GuestStatus.find_by(instance_id=self.DUMMY_INSTANCE_ID).AndReturn({'instance_id': self.DUMMY_INSTANCE_ID, 'state': 'running'})

        # Setup the quotas
        default_quotas = [{ "tenant_id": self.tenant, "hard_limit": 5, "resource":"instances"},
                          { "tenant_id": self.tenant, "hard_limit": 10, "resource":"snapshots"}]
        
        self.mock.StubOutWithMock(models.Quota, 'find_all')
        models.Quota.find_all(tenant_id=self.tenant, deleted=False).AndReturn(default_quotas)
#        models.Quota.find_all(tenant_id=self.tenant, deleted=False).AndReturn(default_quotas)
        
        # Ensure credential comes back
        self.mock.StubOutWithMock(models.Credential, 'find_by')
        models.Credential.find_by(type='object-store').AndReturn({"id": '999'})

        # Stub out the call to Maxwell        
        self.mock.StubOutWithMock(guest_api.API, 'create_snapshot')
        guest_api.API.create_snapshot(mox.IgnoreArg(),
                                      mox.IgnoreArg(),
                                      mox.IgnoreArg(), 
                                      mox.IgnoreArg(), 
                                      mox.IgnoreArg(),
                                      mox.IgnoreArg()).AndReturn(None)
        
        self.mock.ReplayAll()

        response = self.app.post_json("%s" % (self.snapshots_path), body=body,
                                           headers=self.headers,
                                           )
        self.assertEqual(response.status_int, 201)
        
        
    def test_create_quota_error(self):

        body = {
            "snapshot": {
                "name": "snapshot unit test",
                "instanceId" : self.DUMMY_INSTANCE_ID
            }
        }
        
        # Ensure we give back a 'running' instance
        self.mock.StubOutWithMock(models.GuestStatus, 'find_by')
        models.GuestStatus.find_by(instance_id=self.DUMMY_INSTANCE_ID).AndReturn({'instance_id': self.DUMMY_INSTANCE_ID, 'state': 'running'})

        # Setup the quotas
        default_quotas = [{ "tenant_id": self.tenant, "hard_limit": 5, "resource":"instances"},
                          { "tenant_id": self.tenant, "hard_limit": 0, "resource":"snapshots"}]
        
        self.mock.StubOutWithMock(models.Quota, 'find_all')
        models.Quota.find_all(tenant_id=self.tenant, deleted=False).AndReturn(default_quotas)
        models.Quota.find_all(tenant_id=self.tenant, deleted=False).AndReturn(default_quotas)
        
        self.mock.ReplayAll()

        response = self.app.post_json("%s" % (self.snapshots_path), body=body,
                                           headers=self.headers, expect_errors=True
                                           )
        
        self.assertEqual(response.status_int, 413)

 
