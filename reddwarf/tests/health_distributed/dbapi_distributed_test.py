#    Copyright 2012 Hewlett-Packard Development Company, L.P.
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

# NOTE: To run this health check, you will need OS_TENANT_NAME and OS_PASSWORD
# declared either in your system environment variables or in your IDE run
# configuration for this file!


#                  ######### Test Coverage #########
#     (X = covered, O = not covered, - = not covered but unnecessary)
#
#                With body    Without body    Malformed body    Instance not ready
#
#(Instances)
#Create            X           X               X                 -
#Delete            X           X               -                 -
#Show              X           X               -                 -
#Show All          X           X               -                 -
#Restart           X           X               -                 X
#Change password   X           X               -                 X
#
#(Snapshots)
#Create            X           X               X                 -
#Delete            X           X               -                 -
#Show              X           X               -                 - 
#Show All          X           X               -                 -
#Apply             X           X               X                 -

import logging
import unittest
import json
import httplib2
import os
import time

AUTH_URL = "https://region-a.geo-1.identity.hpcloudsvc.com:35357/v2.0/tokens"
TENANT_NAME = os.environ['DBAAS_TENANT_NAME']
USERNAME = os.environ['DBAAS_USERNAME']
PASSWORD = os.environ['DBAAS_PASSWORD']
API_ENDPOINT = os.environ['DBAAS_ENDPOINT']


# Try to authenticate with HP Cloud
KEYSTONE_HEADER = {"Content-Type": "application/json",
                   "User-Agent": "python-novaclient"}

KEYSTONE_BODY = r'''{"auth": {"tenantName": "%s", "passwordCredentials": {"username": "%s", "password": "%s"}}}''' % (TENANT_NAME, USERNAME, PASSWORD)

req = httplib2.Http(".cache")
resp, content = req.request(AUTH_URL, "POST", KEYSTONE_BODY, KEYSTONE_HEADER)
content = json.loads(content)

AUTH_TOKEN = content['access']['token']['id']
AUTH_HEADER = {'X-Auth-Token': AUTH_TOKEN, 
               'content-type': 'application/json', 
               'Accept': 'application/json',
               'X-Auth-Project-Id': '%s' % TENANT_NAME}

TENANT_ID = content['access']['token']['tenant']['id']
API_URL = API_ENDPOINT + "/v1.0/" + TENANT_ID + "/"

logging.basicConfig()
LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)

LOG.debug("Response from Keystone: %s" % content)
LOG.debug("Using Auth-Token %s" % AUTH_TOKEN)
LOG.debug("Using Auth-Header %s" % AUTH_HEADER)


from reddwarf.db import db_api
from reddwarf.common import config
from reddwarf.common import utils
from reddwarf.database import utils as rd_utils
from reddwarf.database import models
from reddwarf.database import worker_api

SQL_CONNECTION = os.environ['SQL_CONNECTION']
RABBIT_HOST = os.environ['RABBIT_HOST']
RABBIT_USER = os.environ['RABBIT_USER']
RABBIT_PASSWORD = os.environ['RABBIT_PASSWORD']

INSTANCE_NAME = 'dbapi_dist_health_' + utils.generate_uuid()


class DistributedCreateTest(unittest.TestCase):

    def setUp(self):
        options = { 'sql_connection' : 'mysql://vipul:tapasiya@15.185.163.25/reddwarf' }
        db_api.configure_db(options)
        
        config.Config.instance = { "rabbit_host" : RABBIT_HOST,
                                   "rabbit_userid" : "guest",
                                   "rabbit_password" : "guest",
                                   "rabbit_virtual_host" : "/",
                                   "rabbit_port" : "5671",
                                   "rabbit_use_ssl" : "True" }
        
        super(DistributedCreateTest, self).setUp()

    def test_create_instance(self):
        image_id, flavor_id, keypair_name, region_az, credential = self._load_boot_params(TENANT_ID)
        
        remote_hostname = utils.generate_uuid()
        
        try:
            db_instance = models.DBInstance().create(name=INSTANCE_NAME,
                                     status='building',
                                     remote_hostname=remote_hostname,
                                     tenant_id=TENANT_ID,
                                     credential=credential['id'],
                                     port='3306',
                                     flavor=1,
                                     availability_zone=region_az)
            
        except Exception, e:
            LOG.exception("Error creating DB Instance record")
            self.fail("Could not create a DB Instance record")
            
        LOG.debug("Wrote DB Instance: %s" % db_instance)
        
        instance_id = db_instance['id']
        
        # Add a GuestStatus record pointing to the new instance for Maxwell
        try:
            guest_status = models.GuestStatus().create(instance_id=db_instance['id'], state='building')
        except Exception, e:
            LOG.exception("Error creating GuestStatus instance %s" % db_instance.data()['id'])
            self.fail("Unable to create GuestStatus entry")
            
        file_dict = { '/home/nova/agent.config': rd_utils.create_boot_config(config.Config, None, None, 'test') }
        
        instance = { 'id' : instance_id,
                     'remote_uuid' : None,
                     'remote_hostname' : remote_hostname,
                     'tenant_id' : TENANT_ID
                    }
        
        # Invoke worker to ensure instance gets created
        worker_api.API().ensure_create_instance(None, instance, rd_utils.file_dict_as_userdata(file_dict))
        
        

        # Test getting a specific db instance.
        # ------------------------------------
        LOG.info("* Getting instance %s" % instance_id)
        resp, content = req.request(API_URL + "instances/" + instance_id, "GET", "", AUTH_HEADER)
        self.assertEqual(200, resp.status, ("Expecting 200 as response status of show instance but received %s" % resp.status))

        # Check to see if the instance created is 
        # in the 'running' state
                
        # wait a max of 15 minutes for instance to come up
        max_wait_for_instance = 960 

        wait_so_far = 0
        LOG.debug("Content: %s" % content)
        content = json.loads(content)
        status = content['instance']['status']
        while (status != 'running'):
            # wait a max of max_wait for instance status to show running
            time.sleep(10)
            wait_so_far += 10
            if wait_so_far >= max_wait_for_instance:
                break
            
            resp, content = req.request(API_URL + "instances/" + instance_id, "GET", "", AUTH_HEADER)
            self.assertEqual(200, resp.status, ("Expecting 200 as response status of show instance but received %s" % resp.status))

            LOG.debug("Content: %s" % content)
            content = json.loads(content)
            status = content['instance']['status']
            
        self.assertTrue(status == 'running', ("Instance %s did not go to running after waiting 16 minutes" % instance_id))

    def _load_boot_params(self, tenant_id):
        # Attempt to find Boot parameters for a specific tenant
        try:
            service_image = models.ServiceImage.find_by(service_name="database", tenant_id=tenant_id, deleted=False)
        except models.ModelNotFoundError, e:
            LOG.info("Service Image for tenant %s not found, using image for 'default_tenant'" % tenant_id)
            service_image = models.ServiceImage.find_by(service_name="database", tenant_id='default_tenant', deleted=False)

        image_id = service_image['image_id']
        
        flavor = models.ServiceFlavor.find_by(service_name="database", deleted=False)
        flavor_id = flavor['flavor_id']

        service_keypair = models.ServiceKeypair.find_by(service_name='database', deleted=False)
        keypair_name = service_keypair['key_name']
        
        try:
            service_zone = models.ServiceZone.find_by(service_name='database', tenant_id=tenant_id, deleted=False)
        except models.ModelNotFoundError, e:
            LOG.info("Service Zone for tenant %s not found, using zone for 'default_tenant'" % tenant_id)
            service_zone = models.ServiceZone.find_by(service_name='database', tenant_id='default_tenant', deleted=False)

        region_az = service_zone['availability_zone']
        
        # Get the credential to use for proxy compute resource
        credential = models.Credential.find_by(type='compute', deleted=False)
        
        LOG.debug("Using ImageID %s" % image_id)
        LOG.debug("Using FlavorID %s" % flavor_id)
        LOG.debug("Using Keypair %s" % keypair_name)
        LOG.debug("Using Region %s" % region_az)
        
        return (image_id, flavor_id, keypair_name, region_az, credential)
            

    def tearDown(self):
        """Run a clean-up check to catch orphaned instances/snapshots due to
           premature test failures."""

        LOG.info("\n*** Starting cleanup...")
        req = httplib2.Http(".cache")

        # Delete all orphaned instances and snapshots
        LOG.info("- Deleting orphaned instances:")
        resp, content = req.request(API_URL + "instances", "GET", "", AUTH_HEADER)
        content = json.loads(content)
#        LOG.debug("CONTENT: %s" % content)

        for each in content['instances']:
#            LOG.debug("EACH: %s" % each)
            if each['name'] == INSTANCE_NAME:               
                LOG.info("Deleting instance: %s" % each['id'])
                resp, content = req.request(API_URL + "instances/" + each['id'], "DELETE", "", AUTH_HEADER)
                LOG.debug(resp)
                LOG.debug(content)

