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

import logging
import unittest
import json
import httplib2
import os
import time

TENANT_ID = "21343820976858"
API_URL = "http://15.185.172.176:80/v1.0/" + TENANT_ID + "/"
AUTH_URL = "https://region-a.geo-1.identity.hpcloudsvc.com:35357/auth/v1.0"
X_AUTH_PROJECT_ID = os.environ['OS_TENANT_NAME']
X_AUTH_KEY = os.environ['OS_PASSWORD']

# Try to authenticate with HP Cloud
KEYSTONE_HEADER = {"X-Auth-User": "21343820976858:%s" % os.environ['OS_TENANT_NAME'],
                   "X-Auth-Key": "%s" % X_AUTH_KEY}
req = httplib2.Http(".cache")
resp, content = req.request(AUTH_URL, "GET", "", KEYSTONE_HEADER)
content = json.loads(content)

AUTH_TOKEN = content['access']['token']['id']
AUTH_HEADER = {'X-Auth-Token': AUTH_TOKEN, 
               'content-type': 'application/json', 
               'Accept': 'application/json',
               'X-Auth-Project-Id': '%s' % X_AUTH_PROJECT_ID}

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
        LOG.debug("* Creating db instance")
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
        LOG.debug("* Creating an instance without a body")
        resp, content = req.request(API_URL + "instances", "POST", "", AUTH_HEADER)
        LOG.debug(resp)
        LOG.debug(content)

        # Assert 1) that the request was not accepted
        self.assertEqual(404, resp.status)


        # Test listing all db instances.
        LOG.debug("* Listing all db instances")
        resp, content = req.request(API_URL + "instances", "GET", "", AUTH_HEADER)
        LOG.debug(content)
        content = json.loads(content)
        LOG.debug(resp)
        LOG.debug(content)

        # Assert 1) that the request was accepted and 2) that the response is
        # in the expected format (e.g. a JSON object beginning with an
        # 'instances' key).
        self.assertEqual(200, resp.status)
        LOG.debug(content)
        self.assertTrue(content.has_key('instances'))


        # Test listing all db instances with a body in the request.
        LOG.debug("* Listing all db instances with a body")
        resp, content = req.request(API_URL + "instances", "GET", body, AUTH_HEADER)
        LOG.debug(resp)
        LOG.debug(content)

        # Assert 1) that the request was not accepted
        self.assertEqual(404, resp.status)
        

        # Test getting a specific db instance.
        LOG.debug("* Getting instance %s" % self.instance_id)
        resp, content = req.request(API_URL + "instances/" + self.instance_id, "GET", "", AUTH_HEADER)
        content = json.loads(content)
        LOG.debug(resp)
        LOG.debug(content)

        # Assert 1) that the request was accepted and 2) that the returned
        # instance is the same as the accepted instance.
        self.assertEqual(200, resp.status)
        self.assertEqual(self.instance_id, str(content['instance']['id']))


        # Test getting a specific db instance with a body in the request.
        LOG.debug("* Getting instance %s with a body in the request" % self.instance_id)
        resp, content = req.request(API_URL + "instances/" + self.instance_id, "GET", body, AUTH_HEADER)
        LOG.debug(resp)
        LOG.debug(content)

        # Assert 1) that the request was not accepted
        self.assertEqual(404, resp.status)


        # Test getting a non-existent db instance.
        LOG.debug("* Getting dummy instance")
        resp, content = req.request(API_URL + "instances/dummy", "GET", "", AUTH_HEADER)
        content = json.loads(content)
        LOG.debug(resp)
        LOG.debug(content)

        # Assert 1) that the request was not accepted
        self.assertEqual(404, resp.status)


        # Test immediately resetting the password on a db instance.
        LOG.debug("* Resetting password on instance %s" % self.instance_id)
        resp, content = req.request(API_URL + "instances/" + self.instance_id + "/resetpassword", "POST", "", AUTH_HEADER)
        LOG.debug(resp)
        LOG.debug(content)

        # Assert 1) that the request was accepted.
        self.assertNotEqual(200, resp.status)


        # Test immediately resetting the password on a db instance with a body in the request.
        LOG.debug("* Resetting password on instance %s with a body in the request" % self.instance_id)
        resp, content = req.request(API_URL + "instances/" + self.instance_id + "/resetpassword", "POST", body, AUTH_HEADER)
        LOG.debug(resp)
        LOG.debug(content)

        # Assert 1) that the request was not accepted.
        self.assertEqual(404, resp.status)
        

        # Test resetting the password on a db instance for a non-existent instance
        LOG.debug("* Resetting password on dummy instance")
        resp, content = req.request(API_URL + "instances/dummy/resetpassword", "POST", "", AUTH_HEADER)
        LOG.debug(resp)
        LOG.debug(content)

        # Assert 1) that the request was not accepted 
        self.assertEqual(404, resp.status) 
        

        # Test immediately restarting a db instance.
        LOG.debug("* Restarting instance %s" % self.instance_id)
        resp, content = req.request(API_URL + "instances/" + self.instance_id + "/restart", "POST", "", AUTH_HEADER)
        LOG.debug(resp)
        LOG.debug(content)

        # Assert 1) that the request was accepted but raised an exception
        # (because the server isn't ready to be rebooted yet).
        self.assertNotEqual(200, resp.status)
        

        # Test immediately restarting a db instance with a body in the request.
        LOG.debug("* Restarting instance %s" % self.instance_id)
        resp, content = req.request(API_URL + "instances/" + self.instance_id + "/restart", "POST", body, AUTH_HEADER)
        LOG.debug(resp)
        LOG.debug(content)

        # Assert 1) that the request was not accepted
        self.assertEqual(404, resp.status)
        
 
        # Test restarting a db instance for a non-existent instance
        LOG.debug("* Restarting dummy instance")
        resp, content = req.request(API_URL + "instances/dummy/restart", "POST", "", AUTH_HEADER)
        LOG.debug(resp)
        LOG.debug(content)

        # Assert 1) that the request was not accepted 
        self.assertEqual(404, resp.status)       
                

        # TODO: add a sleep and re-test reset password and reboot instance


        # Test deleting a db instance.
        LOG.debug("* Deleting instance %s" % self.instance_id)
        resp, content = req.request(API_URL + "instances/" + self.instance_id, "DELETE", "", AUTH_HEADER)
        LOG.debug(resp)
        LOG.debug(content)

        # Assert 1) that the request was accepted and 2) that the instance has
        # been deleted.
        self.assertEqual(204, resp.status)

        LOG.debug("Verifying that instance %s has been deleted" % self.instance_id)
        resp, content = req.request(API_URL + "instances", "GET", "", AUTH_HEADER)
        LOG.debug("Returned from listing...")
        LOG.debug(resp)
        LOG.debug(content)
        
        if content == []:
            pass
        else:
            content = json.loads(content)
            for each in content['instances']:
                self.assertFalse(each['id'] == self.instance_id)

        LOG.debug("Sleeping...")
        time.sleep(10)


        # Test deleting an instance with a body in the request.
        LOG.debug("Testing delete of instance %s with a body in the request" % self.instance_id)
        resp, content = req.request(API_URL + "instances/" + self.instance_id, "DELETE", body, AUTH_HEADER)
        LOG.debug(resp)
        LOG.debug(content)

        # Assert 1) that the request was not accepted
        self.assertEqual(404, resp.status)
        

        # Test that trying to delete an already deleted instance returns
        # the proper error code.
        LOG.debug("Testing re-delete of instance %s" % self.instance_id)
        resp, content = req.request(API_URL + "instances/" + self.instance_id, "DELETE", "", AUTH_HEADER)
        LOG.debug(resp)
        LOG.debug(content)

        # Assert 1) that the request was accepted and 2) that the right error
        # code is returned.
        self.assertEqual(404, resp.status)


    def test_snapshot_api(self):
        """Comprehensive snapshot API test using a snapshot lifecycle."""

        # Create an image for snapshot purposes.
        LOG.debug("* Creating db instance")
        body = r"""
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

        req = httplib2.Http(".cache")
        resp, content = req.request(API_URL + "instances", "POST", body, AUTH_HEADER)
        content = json.loads(content)
        LOG.debug(resp)
        LOG.debug(content)

        self.instance_id = content['instance']['id']
        LOG.debug("Instance ID: %s" % self.instance_id)

        """Assert 1) that the request was accepted and 2) that the response
           is in the expected format."""
        self.assertEqual(201, resp.status)
        self.assertTrue(content.has_key('instance'))


        # Test creating a db snapshot immediately after creation.
        LOG.debug("* Creating immediate snapshot for instance %s" % self.instance_id)
        body = r"""{ "snapshot": { "instanceId": """ + "\"" + self.instance_id + "\"" + r""", "name": "dbapi_test" } }"""
        resp, content = req.request(API_URL + "snapshots", "POST", body, AUTH_HEADER)
        LOG.debug(resp)
        LOG.debug(content)

        # Assert 1) that the request was accepted and 2) that the response
        # is in the proper format.
        self.assertEqual(423, resp.status)
        
        # wait a max of 5 minutes for instance to come up
        max_wait_for_instance = 300 
        # Will likely get a 423 since instance is not ready
        if resp['status'] == '423':
            LOG.debug("expected 423 response since instance not ready")
            
            # Test getting a specific db instance.
            LOG.debug("* Getting instance %s" % self.instance_id)
            resp, content = req.request(API_URL + "instances/" + self.instance_id, "GET", "", AUTH_HEADER)
            content = json.loads(content)
            
            wait_so_far = 0
            status = content['instance']['status']
            while (status is not 'running'):
                # wait a max of max_wait for instance status to show running
                time.sleep(10)
                wait_so_far += 10
                if wait_so_far >= max_wait_for_instance:
                    break
                
                resp, content = req.request(API_URL + "instances/" + self.instance_id, "GET", "", AUTH_HEADER)
                content = json.loads(content)
                status = content['instance']['status']
                
            self.assertTrue(status == 'running')

            body = r"""{ "snapshot": { "instanceId": """ + "\"" + self.instance_id + "\"" + r""", "name": "dbapi_test" } }"""
            resp, content = req.request(API_URL + "snapshots", "POST", body, AUTH_HEADER)
            LOG.debug(resp)
            LOG.debug(content)

        try:
            content = json.loads(content)
        except Exception, err:
            LOG.error(err)
            LOG.error("Create snapshot - Error processing JSON object: %s" % content)
            self.assertEqual(True, False)
    
        self.snapshot_id = content['snapshot']['id']
        LOG.debug("Snapshot ID: %s" % self.snapshot_id)

        # Assert 1) that the request was accepted and 2) that the response
        # is in the proper format.
        self.assertEqual(201, resp.status)
        self.assertTrue(content.has_key('snapshot'))
        self.assertEqual(self.instance_id, content['snapshot']['instanceId'])
        
        
        # Test creating an instance without a body in the request.
        LOG.debug("* Creating an snapshot without a body")
        resp, content = req.request(API_URL + "snapshots", "POST", "", AUTH_HEADER)
        LOG.debug(resp)
        LOG.debug(content)

        # Assert 1) that the request was not accepted
        self.assertEqual(404, resp.status)


        # Test listing all db snapshots.
        LOG.debug("* Listing all snapshots")
        resp, content = req.request(API_URL + "snapshots", "GET", "", AUTH_HEADER)
        LOG.debug(resp)
        LOG.debug(content)
        try:
            content = json.loads(content)
        except Exception, err:
            LOG.error(err)
            LOG.error("List all snapshots - Error processing JSON object: %s" % content)
            self.assertEqual(True, False)

        # Assert 1) that the request was accepted and 2) that the response
        # is in the proper format.
        self.assertEqual(200, resp.status)
        self.assertTrue(content.has_key('snapshots'))


        # Test listing all snapshots with a body in the request.
        LOG.debug("* Listing all snapshots with a body")
        resp, content = req.request(API_URL + "snapshots", "GET", body, AUTH_HEADER)
        LOG.debug(resp)
        LOG.debug(content)

        # Assert 1) that the request was not accepted
        self.assertEqual(404, resp.status)


        # Test listing all db snapshots for a specific instance.
        LOG.debug("* Listing all snapshots for %s" % self.instance_id)
        resp, content = req.request(API_URL + "snapshots?instanceId=" + self.instance_id, "GET", "", AUTH_HEADER)
        LOG.debug(resp)
        LOG.debug(content)
        try:
            content = json.loads(content)
        except Exception, err:
            LOG.error(err)
            LOG.error("List all snapshots for an instance - Error processing JSON object: %s" % content)
            self.assertEqual(True, False)

        # Assert 1) that the request was accepted, 2) that the response
        # is in the proper format, and 3) that the list contains the created
        # snapshot.
        self.assertEqual(200, resp.status)
        self.assertTrue(content.has_key('snapshots'))
        found = False
        for each in content['snapshots']:
            if self.snapshot_id == each['id'] and \
               self.instance_id == each['instanceId']:
                found = True
        self.assertEqual(True, found)


        # Test listing all snapshots for a specific instance with a body in the request.
        LOG.debug("* Listing all snapshots for a specific instance with a body")
        resp, content = req.request(API_URL + "snapshots?instanceId=" + self.instance_id, "GET", body, AUTH_HEADER)
        LOG.debug(resp)
        LOG.debug(content)

        # Assert 1) that the request was not accepted
        self.assertEqual(404, resp.status)
        
  
        # Test listing all db snapshots for a specific tenant.
        LOG.debug("* Listing all snapshots for %s" % TENANT_ID)
        resp, content = req.request(API_URL + "snapshots?tenantId=" + TENANT_ID, "GET", "", AUTH_HEADER)
        LOG.debug(resp)
        LOG.debug(content)
        try:
            content = json.loads(content)
        except Exception, err:
            LOG.error(err)
            LOG.error("List all snapshots for an tenant - Error processing JSON object: %s" % content)
            self.assertEqual(True, False)

        # Assert 1) that the request was accepted, 2) that the response
        # is in the proper format, and 3) that the list contains the created
        # snapshot.
        self.assertEqual(200, resp.status)
        self.assertTrue(content.has_key('snapshots'))
        found = False
        for each in content['snapshots']:
            if self.snapshot_id == each['id'] and \
               self.instance_id == each['instanceId']:
                found = True
        self.assertEqual(True, found)      
        

        # Test listing all snapshots for a specific tenant with a body in the request.
        LOG.debug("* Listing all snapshots for a specific instance with a body")
        resp, content = req.request(API_URL + "snapshots?tenantId=" + TENANT_ID, "GET", body, AUTH_HEADER)
        LOG.debug(resp)
        LOG.debug(content)

        # Assert 1) that the request was not accepted
        self.assertEqual(404, resp.status)
        

        # Test getting details about a specific db snapshot.
        LOG.debug("* Listing snapshot %s" % self.snapshot_id)
        resp, content = req.request(API_URL + "snapshots/" + self.snapshot_id, "GET", "", AUTH_HEADER)
        LOG.debug(resp)
        LOG.debug(content)
        try:
            content = json.loads(content)
        except Exception, err:
            LOG.error(err)
            LOG.error("Listing specific snapshot - Error processing JSON object: %s" % content)
            self.assertEqual(True, False)

        # Assert 1) that the request was accepted, 2) that the response
        # is in the proper format, and 3) that the response is the correct
        # snapshot.
        self.assertEqual(200, resp.status)
        self.assertTrue(content.has_key('snapshot'))
        self.assertEqual(self.instance_id, content['snapshot']['instanceId'])
        self.assertEqual(self.snapshot_id, content['snapshot']['id'])


        # Test getting a non-existent snapshot.
        LOG.debug("* Getting dummy snapshot")
        resp, content = req.request(API_URL + "snapshots/dummy", "GET", "", AUTH_HEADER)
        content = json.loads(content)
        LOG.debug(resp)
        LOG.debug(content)

        # Assert 1) that the request was not accepted
        self.assertEqual(404, resp.status)
        

        # Test deleting a db snapshot.
        LOG.debug("* Deleting snapshot %s" % self.snapshot_id)
        resp, content = req.request(API_URL + "snapshots/" + self.snapshot_id, "DELETE", "", AUTH_HEADER)
        LOG.debug(resp)
        LOG.debug(content)

        # Assert 1) that the request was accepted and 2) that the snapshot
        # has been deleted.
        self.assertEqual(204, resp.status)

        resp, content = req.request(API_URL + "snapshots/" + self.snapshot_id, "GET", "", AUTH_HEADER)
        LOG.debug(resp)
        LOG.debug(content)
        self.assertEqual(404, resp.status)
        
        
        # Test deleting a non-existent snapshot.
        LOG.debug("* Deleting dummy snapshot")
        resp, content = req.request(API_URL + "snapshots/dummy", "DELETE", "", AUTH_HEADER)
        content = json.loads(content)
        LOG.debug(resp)
        LOG.debug(content)

        # Assert 1) that the request was not accepted
        self.assertEqual(404, resp.status)
              

        time.sleep(10)

        # Finally, delete the instance.
        LOG.debug("* Deleting instance %s" % self.instance_id)
        resp, content = req.request(API_URL + "instances/" + self.instance_id, "DELETE", "", AUTH_HEADER)
        LOG.debug(resp)
        LOG.debug(content)

        # Assert 1) that the request was accepted and 2) that the instance has
        # been deleted.
        self.assertEqual(204, resp.status)

        resp, content = req.request(API_URL + "instances", "GET", "", AUTH_HEADER)
        try:
            content = json.loads(content)
        except Exception, err:
            LOG.error(err)
            LOG.error("Deleting instance used for snapshots - Error processing JSON object: %s" % content)
            self.assertEqual(True, False)

        LOG.debug(content)
        for each in content['instances']:
            self.assertFalse(each['id'] == self.instance_id)

    def tearDown(self):
        """Run a clean-up check to catch orphaned instances/snapshots due to
           premature test failures."""

        LOG.debug("\n*** Starting cleanup...")
        req = httplib2.Http(".cache")

        # Get list of snapshots
        LOG.debug("- Getting list of snapshots")
        resp, snapshots = req.request(API_URL + "snapshots", "GET", "", AUTH_HEADER)        
        snapshots = json.loads(snapshots)

        # Delete all orphaned instances and snapshots
        LOG.debug("- Deleting orphaned instances:")
        resp, content = req.request(API_URL + "instances", "GET", "", AUTH_HEADER)
        content = json.loads(content)
#        LOG.debug("CONTENT: %s" % content)

        for each in content['instances']:
#            LOG.debug("EACH: %s" % each)
            if each['name'] == "dbapi_test":
                for snapshot in snapshots['snapshots']:
                    # If any snapshots belong to an instance to be deleted, delete the snapshots too
                    if snapshot['instanceId'] == each['id']:
                        LOG.debug("Deleting snapshot: %s" % snapshot['id'])
                        resp, content = req.request(API_URL + "snapshots/" + snapshot['id'], "DELETE", "", AUTH_HEADER)
                        LOG.debug(resp)
                        LOG.debug(content)                        
                LOG.debug("Deleting instance: %s" % each['id'])
                resp, content = req.request(API_URL + "instances/" + each['id'], "DELETE", "", AUTH_HEADER)
                LOG.debug(resp)
                LOG.debug(content)

