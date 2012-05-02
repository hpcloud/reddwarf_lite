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
X_AUTH_PROJECT_ID = os.environ['OS_TENANT_NAME']
AUTH_TOKEN = os.environ['OS_PASSWORD']
API_ENDPOINT = os.environ['DBAAS_ENDPOINT']

# Try to authenticate with HP Cloud
KEYSTONE_HEADER = {"Content-Type": "application/json",
                   "User-Agent": "python-novaclient"}

KEYSTONE_BODY = r'''{"auth": {"tenantName": "%s", "passwordCredentials": {"username": "%s", "password": "%s"}}}''' % (X_AUTH_PROJECT_ID, X_AUTH_PROJECT_ID, AUTH_TOKEN)

print KEYSTONE_BODY
req = httplib2.Http(".cache")
resp, content = req.request(AUTH_URL, "POST", KEYSTONE_BODY, KEYSTONE_HEADER)
print content
content = json.loads(content)

AUTH_TOKEN = content['access']['token']['id']
AUTH_HEADER = {'X-Auth-Token': AUTH_TOKEN, 
               'content-type': 'application/json', 
               'Accept': 'application/json',
               'X-Auth-Project-Id': '%s' % X_AUTH_PROJECT_ID}

TENANT_ID = content['access']['token']['tenant']['id']
API_URL = API_ENDPOINT + "/v1.0/" + TENANT_ID + "/"

logging.basicConfig()
LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)

LOG.debug("Response from Keystone: %s" % content)
LOG.debug("Using Auth-Token %s" % AUTH_TOKEN)
LOG.debug("Using Auth-Header %s" % AUTH_HEADER)

class DBFunctionalTests(unittest.TestCase):

    def test_instance_api(self):
        
        """Comprehensive instance API test using an instance lifecycle."""

        # Test creating a db instance.
        LOG.info("* Creating db instance")
        body = r"""
        {"instance": {
            "name": "dbapi_distributed_test",
            "flavorRef": "medium",
            "port": "3306",
            "dbtype": {
                "name": "mysql",
                "version": "5.5"
                }
            }
        }"""

        req = httplib2.Http(".cache")
        resp, content = req.request(API_URL + "instances", "POST", body, AUTH_HEADER)
        LOG.debug(content)
        content = json.loads(content)
        LOG.debug(resp)
        LOG.debug(content)

        self.instance_id = content['instance']['id']
        LOG.debug("Instance ID: %s" % self.instance_id)

        # Assert 1) that the request was accepted and 2) that the response
        # is in the expected format.
        self.assertEqual(201, resp.status, "Response status of create instance not 201")
        self.assertTrue(content.has_key('instance'), "Response body of create instance does not have 'instance' field")

        # Test getting a specific db instance.
        LOG.info("* Getting instance %s" % self.instance_id)
        resp, content = req.request(API_URL + "instances/" + self.instance_id, "GET", "", AUTH_HEADER)
        content = json.loads(content)
        LOG.debug(resp)
        LOG.debug(content)

        # Assert 1) that the request was accepted and 2) that the returned
        # instance is the same as the accepted instance.
        self.assertEqual(200, resp.status, "Response status of show instance not 200")
        self.assertEqual(self.instance_id, str(content['instance']['id']), "Instance ID not found in Show Instance response")


        # Check to see if the instance we previously created is 
        # in the 'running' state
                
        # wait a max of 5 minutes for instance to come up
        max_wait_for_instance = 960 

        wait_so_far = 0
        status = content['instance']['status']
        while (status != 'running'):
            # wait a max of max_wait for instance status to show running
            time.sleep(10)
            wait_so_far += 10
            if wait_so_far >= max_wait_for_instance:
                break
            
            resp, content = req.request(API_URL + "instances/" + self.instance_id, "GET", "", AUTH_HEADER)
            LOG.debug("Content: %s" % content)
            content = json.loads(content)
            status = content['instance']['status']
            
        self.assertTrue(status == 'running', ("Instance %s did not go to running after waiting 5 minutes" % self.instance_id))

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
            if each['name'] == "dbapi_distributed_test":               
                LOG.info("Deleting instance: %s" % each['id'])
                resp, content = req.request(API_URL + "instances/" + each['id'], "DELETE", "", AUTH_HEADER)
                LOG.debug(resp)
                LOG.debug(content)

