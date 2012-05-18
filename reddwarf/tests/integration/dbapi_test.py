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

    def xtest_instance_api_negative(self):
        """Comprehensive instance API test using an instance lifecycle."""

        # Test creating a db instance.
        LOG.info("* Creating db instance")
        body = r"""
        {"instance": {
            "name": "dbapi_test",
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
        self.assertEqual(201, resp.status)
        self.assertTrue(content.has_key('instance'))


        # Test creating an instance without a body in the request.
        LOG.info("* Creating an instance without a body")
        resp, content = req.request(API_URL + "instances", "POST", "", AUTH_HEADER)
        LOG.debug(resp)
        LOG.debug(content)
        self.assertEqual(404, resp.status)


        # Test creating an instance with a malformed body.
        LOG.info("* Creating an instance with a malformed body")
        resp, content = req.request(API_URL + "instances", "POST", r"""{"instance": {}}""", AUTH_HEADER)
        LOG.debug(resp)
        LOG.debug(content)
        self.assertEqual(500, resp.status)
        
        # Test listing all db instances with a body in the request.
        LOG.info("* Listing all db instances with a body")
        resp, content = req.request(API_URL + "instances", "GET", body, AUTH_HEADER)
        LOG.debug(resp)
        LOG.debug(content)
        self.assertEqual(404, resp.status)
        
        # Test getting a specific db instance with a body in the request.
        LOG.info("* Getting instance %s with a body in the request" % self.instance_id)
        resp, content = req.request(API_URL + "instances/" + self.instance_id, "GET", body, AUTH_HEADER)
        LOG.debug(resp)
        LOG.debug(content)
        self.assertEqual(404, resp.status)


        # Test getting a non-existent db instance.
        LOG.info("* Getting dummy instance")
        resp, content = req.request(API_URL + "instances/dummy", "GET", "", AUTH_HEADER)
        content = json.loads(content)
        LOG.debug(resp)
        LOG.debug(content)
        self.assertEqual(404, resp.status)


        # Test immediately resetting the password on a db instance with a body in the request.
        LOG.info("* Resetting password on instance %s with a body in the request" % self.instance_id)
        resp, content = req.request(API_URL + "instances/" + self.instance_id + "/resetpassword", "POST", body, AUTH_HEADER)
        LOG.debug(resp)
        LOG.debug(content)
        self.assertEqual(404, resp.status)
        

        # Test resetting the password on a db instance for a non-existent instance
        LOG.info("* Resetting password on dummy instance")
        resp, content = req.request(API_URL + "instances/dummy/resetpassword", "POST", "", AUTH_HEADER)
        LOG.debug(resp)
        LOG.debug(content)
        self.assertEqual(404, resp.status) 
        
        # Test restarting a db instance for a non-existent instance
        LOG.info("* Restarting dummy instance")
        resp, content = req.request(API_URL + "instances/dummy/restart", "POST", "", AUTH_HEADER)
        LOG.debug(resp)
        LOG.debug(content)
        self.assertEqual(404, resp.status) 

        # Test immediately restarting a db instance with a body in the request.
        LOG.info("* Restarting instance %s" % self.instance_id)
        resp, content = req.request(API_URL + "instances/" + self.instance_id + "/restart", "POST", body, AUTH_HEADER)
        LOG.debug(resp)
        LOG.debug(content)
        self.assertEqual(404, resp.status)      

        # Test deleting an instance with a body in the request.
        LOG.info("* Testing delete of instance %s with a body in the request" % self.instance_id)
        resp, content = req.request(API_URL + "instances/" + self.instance_id, "DELETE", body, AUTH_HEADER)
        LOG.debug(resp)
        LOG.debug(content)
        self.assertEqual(404, resp.status)

        # Test that trying to delete an already deleted instance returns
        # the proper error code.
        LOG.info("* Testing re-delete of instance %s" % self.instance_id)
        resp, content = req.request(API_URL + "instances/" + self.instance_id, "DELETE", "", AUTH_HEADER)
        LOG.debug(resp)
        LOG.debug(content)
        self.assertEqual(404, resp.status)

    def xtest_snapshot_api(self):
        """Comprehensive snapshot API test using a snapshot lifecycle."""

        req = httplib2.Http(".cache")
        body = r"""{ "snapshot": { "instanceId": "123", "name": "dbapi_test" } }"""
                
        # Test creating an snapshot without a body in the request.
        LOG.info("* Creating an snapshot without a body")
        resp, content = req.request(API_URL + "snapshots", "POST", "", AUTH_HEADER)
        LOG.debug(resp)
        LOG.debug(content)
        self.assertEqual(404, resp.status)

        # Test creating an snapshot with a malformed body.
        LOG.info("* Creating an snapshot with a malformed body")
        bad_body = r"""{ "snapshot": {}]"""
        resp, content = req.request(API_URL + "snapshots", "POST", bad_body, AUTH_HEADER)
        LOG.debug(resp)
        LOG.debug(content)
        self.assertEqual(500, resp.status)

        # Test listing all snapshots with a body in the request.
        LOG.info("* Listing all snapshots with a body")
        resp, content = req.request(API_URL + "snapshots", "GET", body, AUTH_HEADER)
        LOG.debug(resp)
        LOG.debug(content)
        self.assertEqual(404, resp.status)

        # Test listing all snapshots for a specific instance with a body in the request.
        LOG.info("* Listing all snapshots for a specific instance with a body")
        resp, content = req.request(API_URL + "snapshots?instanceId=" + self.instance_id, "GET", body, AUTH_HEADER)
        LOG.debug(resp)
        LOG.debug(content)
        self.assertEqual(404, resp.status)   

        # Test listing all snapshots for a specific tenant with a body in the request.
        LOG.info("* Listing all snapshots for a specific instance with a body")        
        resp, content = req.request(API_URL + "snapshots?tenantId=" + TENANT_ID, "GET", body, AUTH_HEADER)
        LOG.debug(resp)
        LOG.debug(content)
        self.assertEqual(404, resp.status)

        # Test getting a non-existent snapshot.
        LOG.info("* Getting dummy snapshot")
        resp, content = req.request(API_URL + "snapshots/dummy", "GET", "", AUTH_HEADER)
        content = json.loads(content)
        LOG.debug(resp)
        LOG.debug(content)
        self.assertEqual(404, resp.status)
        
        # Test creating a new instance from a dummy snapshot.
        instance_body = r"""
        {"instance": {
            "name": "dbapi_test",
            "flavorRef": "102",
            "port": "3306",
            "dbtype": {
                "name": "mysql",
                "version": "5.1.2"
            },
            "databases": [
                {
                    "name": "testdb",
                    "character_set": "utf8",
                    "collate": "utf8_general_ci"
                },
                {
                    "name": "abcdefg"
                }
            ],
            "volume":
                {
                    "size": "2"
                }
            }
        }"""
        
        LOG.info("* Creating instance from dummy snapshot")
        snap_body = json.loads(instance_body)
        snap_body['instance']['snapshotId'] = "dummy"
        snap_body = json.dumps(snap_body)
        resp, content = req.request(API_URL + "instances", "POST", snap_body, AUTH_HEADER)
        LOG.debug(resp)
        LOG.debug(content)
        content = json.loads(content)
        self.assertEqual(500, resp.status)
        
        # This test is handled by the error handling in the API server
#        # Test creating a new instance from bad snapshot data in the body.
#        LOG.debug("* Creating instance from bad snapshot data in the body")
#        snap_body = json.loads(instance_body)
#        snap_body['instance']['snapshotId'] = {}
#        snap_body = json.dumps(snap_body)
#        resp, content = req.request(API_URL + "instances", "POST", snap_body, AUTH_HEADER)
#        LOG.debug(resp)
#        LOG.debug(content)
#        content = json.loads(content)
#        self.assertEqual(500, resp.status)        
        
        # Test deleting a non-existent snapshot.
        LOG.info("* Deleting dummy snapshot")
        resp, content = req.request(API_URL + "snapshots/dummy", "DELETE", "", AUTH_HEADER)
        content = json.loads(content)
        LOG.debug(resp)
        LOG.debug(content)
        self.assertEqual(404, resp.status)

