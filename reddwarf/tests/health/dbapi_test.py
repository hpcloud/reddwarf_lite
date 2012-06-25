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
import telnetlib
import os
import time
import MySQLdb
from reddwarf.common import ssh
from reddwarf.common import utils

AUTH_URL = "https://region-a.geo-1.identity.hpcloudsvc.com:35357/v2.0/tokens"
TENANT_NAME = os.environ['DBAAS_TENANT_NAME']
USERNAME = os.environ['DBAAS_USERNAME']
PASSWORD = os.environ['DBAAS_PASSWORD']
API_ENDPOINT = os.environ['DBAAS_ENDPOINT']

# Try to authenticate with HP Cloud
KEYSTONE_HEADER = {"Content-Type": "application/json",
                   "User-Agent": "python-novaclient"}

KEYSTONE_BODY = r'''{"auth": {"tenantName": "%s", "passwordCredentials": {"username": "%s", "password": "%s"}}}''' % (TENANT_NAME, USERNAME, PASSWORD)

print KEYSTONE_BODY
req = httplib2.Http(".cache")
resp, content = req.request(AUTH_URL, "POST", KEYSTONE_BODY, KEYSTONE_HEADER)
print content
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

UUID_PATTERN = '[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}'

INSTANCE_NAME = 'dbapi_health_' + utils.generate_uuid()
MAX_WAIT_RUNNING = 300

class DBFunctionalTests(unittest.TestCase):

    def test_instance_api(self):
        """Comprehensive instance API test using an instance lifecycle."""

        # Test creating a db instance.
        # ----------------------------
        LOG.info("* Creating db instance")
        body = r"""
        {"instance": {
            "name": "%s",
            "flavorRef": "medium",
            "port": "3306",
            "dbtype": {
                "name": "mysql",
                "version": "5.5"
                }
            }
        }""" % INSTANCE_NAME

        client = httplib2.Http(".cache", disable_ssl_certificate_validation=True)
        resp, content = self._execute_request(client, "instances", "POST", body)

        # Assert 1) that the request was accepted and 2) that the response
        # is in the expected format.
        self.assertEqual(201, resp.status, ("Expecting 201 as response status of create instance but received %s" % resp.status))
        content = self._load_json(content,'Create Instance')
        self.assertTrue(content.has_key('instance'), "Response body of create instance does not have 'instance' field")

        self.instance_id = content['instance']['id']
        LOG.debug("Instance ID: %s" % self.instance_id)


        # Test listing all db instances.
        # ------------------------------
        LOG.info("* Listing all db instances")
        resp, content = self._execute_request(client, "instances", "GET", "")
        
        # Assert 1) that the request was accepted and 2) that the response is
        # in the expected format (e.g. a JSON object beginning with an
        # 'instances' key).
        self.assertEqual(200, resp.status, ("Expecting 200 as response status of list instance but received %s" % resp.status))
        content = self._load_json(content,'List all Instances')
        self.assertTrue(content.has_key('instances'), "Response body of list instances does not contain 'instances' field.")


        # Test getting a specific db instance.
        # ------------------------------------
        LOG.info("* Getting instance %s" % self.instance_id)
        resp, content = self._execute_request(client, "instances/" + self.instance_id, "GET", "")
        
        # Assert 1) that the request was accepted and 2) that the returned
        # instance is the same as the accepted instance.
        self.assertEqual(200, resp.status, ("Expecting 200 as response status of show instance but received %s" % resp.status))
        content = self._load_json(content,'Get Single Instance')
        self.assertEqual(self.instance_id, str(content['instance']['id']), "Instance ID not found in Show Instance response")


        # Check to see if the instance we previously created is 
        # in the 'running' state
        # -----------------------------------------------------
        wait_so_far = 0
        status = content['instance']['status']
        while status != 'running':
            # wait a max of max_wait for instance status to show running
            time.sleep(10)
            wait_so_far += 10
            if wait_so_far >= MAX_WAIT_RUNNING:
                break
            
            resp, content = self._execute_request(client, "instances/" + self.instance_id, "GET", "")
            self.assertEqual(200, resp.status, ("Expecting 200 as response status of show instance but received %s" % resp.status))
            content = self._load_json(content,'Get Single Instance')
            status = content['instance']['status']

        if status != 'running':
            self.fail("for some reason the instance did not switch to 'running' in 5 m" % self.instance_id)

        # Test resetting the password on a db instance.
        # ---------------------------------------------
        LOG.info("* Resetting password on instance %s" % self.instance_id)
        resp, content = self._execute_request(client, "instances/" + self.instance_id +"/resetpassword", "POST", "")
        self.assertEqual(200, resp.status, ("Expecting 200 as response status of reset password but received %s" % resp.status))

        # TODO (vipulsabhaya) Attept to log into with this password
        
        # XXX: Suspect restarting too soon after a "reset password" command is putting the instance in a bad mood on restart
        time.sleep(30)

        # Test restarting a db instance.
        # ------------------------------
        LOG.info("* Restarting instance %s" % self.instance_id)
        resp, content = self._execute_request(client, "instances/" + self.instance_id +"/restart", "POST", "")
        self.assertEqual(204, resp.status, ("Expecting 204 as response status of restart instance but received %s" % resp.status))

        # Test getting a specific db instance.
        LOG.info("* Getting instance %s" % self.instance_id)
        resp, content = self._execute_request(client, "instances/" + self.instance_id , "GET", "")
        self.assertEqual(200, resp.status, ("Expecting 200 as response status of show instance but received %s" % resp.status))
        content = self._load_json(content,'Get Single Instance after Restart')
        
        wait_so_far = 0
        status = content['instance']['status']
        while status != 'running':
            # wait a max of max_wait for instance status to show running
            time.sleep(10)
            wait_so_far += 10
            if wait_so_far >= MAX_WAIT_RUNNING:
                break
            
            resp, content = self._execute_request(client, "instances/" + self.instance_id , "GET", "")
            self.assertEqual(200, resp.status, ("Expecting 200 as response status of show instance but received %s" % resp.status))
            content = self._load_json(content,'Get Single Instance')
            status = content['instance']['status']

        if status != 'running':
            self.fail("Instance %s did not go to running after a reboot and waiting 5 minutes" % self.instance_id)


        # Test deleting a db instance.
        # ----------------------------
        LOG.info("* Deleting instance %s" % self.instance_id)
        resp, content = self._execute_request(client, "instances/" + self.instance_id , "DELETE", "")

        # Assert 1) that the request was accepted and 2) that the instance has
        # been deleted.
        self.assertEqual(204, resp.status, "Response status of instance delete did not return 204")

        LOG.debug("Verifying that instance %s has been deleted" % self.instance_id)
        resp, content = self._execute_request(client, "instances", "GET", "")
        
        if not content:
            pass
        else:
            content = json.loads(content)
            for each in content['instances']:
                self.assertFalse(each['id'] == self.instance_id, ("Instance %s did not actually get deleted" % self.instance_id))

        LOG.debug("Sleeping...")
        time.sleep(10)


    def test_snapshot_api(self):
        """Comprehensive snapshot API test using a snapshot lifecycle."""

        # Create a DB instance for snapshot tests
        # ---------------------------------------
        LOG.info("* Creating db instance")
        instance_body = r"""
        {"instance": {
            "name": "%s",
            "flavorRef": "medium",
            "port": "3306",
            "dbtype": {
                "name": "mysql",
                "version": "5.5"
                }
            }
        }""" % INSTANCE_NAME

        client = httplib2.Http(".cache", disable_ssl_certificate_validation=True)
        resp, content = self._execute_request(client, "instances", "POST", instance_body)
        
        self.assertEqual(201, resp.status, ("Expecting 201 response status to Instance Create but received %s" % resp.status))
        content = self._load_json(content,'Create Instance for Snapshotting')
        self.assertTrue(content.has_key('instance'), "Response body of create instance does not contain 'instance' element")

        credential = content['instance']['credential']

        self.instance_id = content['instance']['id']
        LOG.debug("Instance ID: %s" % self.instance_id)



        # Test creating a db snapshot immediately after creation.
        # -------------------------------------------------------
        LOG.info("* Creating immediate snapshot for instance %s" % self.instance_id)
        body = r"""{ "snapshot": { "instanceId": """ + "\"" + self.instance_id + "\"" + (r""", "name": "%s" } }""" % INSTANCE_NAME)
        resp, content = self._execute_request(client, "snapshots", "POST", body)

        # Assert 1) that the request was not accepted
        self.assertEqual(423, resp.status, ("Expected 423 to immediate snapshot creation, but received %s" % resp.status))
        
        # Ensure the instance is up
        # -------------------------
        LOG.info("* Getting instance %s" % self.instance_id)
        resp, content = self._execute_request(client, "instances/" + self.instance_id , "GET", "")
        self.assertEqual(200, resp.status, ("Expecting 200 response status to Instance Show but received %s" % resp.status))
        content = self._load_json(content,'Get Single Instance')
        
        wait_so_far = 0
        status = content['instance']['status']
        while status != 'running':
            # wait a max of max_wait for instance status to show running
            time.sleep(10)
            wait_so_far += 10
            if wait_so_far >= MAX_WAIT_RUNNING:
                break
            
            resp, content = self._execute_request(client, "instances/" + self.instance_id , "GET", "")
            self.assertEqual(200, resp.status, ("Expecting 200 response status to Instance Show but received %s" % resp.status))
            content = self._load_json(content,'Get Single Instance')
            status = content['instance']['status']

        if status != 'running':
            LOG.info("* instance is still not up after 5 minutes")
            self.fail("Instance %s did not go to running after boot and waiting 5 minutes" % self.instance_id)
        else :
            # Add customized data to the database
            LOG.info("* Creating customized DB and inserting data")
            pub_ip = content['instance']['hostname']
            username = credential['username']
            password = credential['password']
            db_name = 'mysql'

            time.sleep(20)
            LOG.info("* Connecting to mysql on first boot: %s, %s, %s" %(username, password, pub_ip))
            try:
                conn = MySQLdb.connect(host = pub_ip,
                    user = username,
                    passwd = password,
                    db = db_name)
            except MySQLdb.Error as ex:
                LOG.exception("* connecting to mysql on first boot failed:")
                self.fail("connecting to mysql failed using pub ip %s" % pub_ip)

            try:
                db_name = 'food'
                LOG.info("* Creating database %s" % db_name)
                cursor = conn.cursor()
                cursor.execute("CREATE DATABASE IF NOT EXISTS food")
                LOG.info("* database %s created" % db_name)
            except MySQLdb.Error as ex:
                LOG.exception("* creating database %s failed" % db_name)
                self.fail("creating database food encounters error")

            try:
                LOG.info("* creating table")
                cursor.execute("""
                CREATE TABLE product
                (
                  name    CHAR(40),
                  category CHAR(40)
                )
                """)
                LOG.info("* table product created")
                LOG.info("* inserting data into table")
                cursor.execute("""
                INSERT INTO product (name, category)
                VALUES
                    ('apple', 'fruits'),
                    ('tomato', 'vegetables'),
                    ('broccoli', 'vegetables')
                """)
                LOG.info("* Number of rows inserted: %d" %cursor.rowcount)
            except MySQLdb.Error as ex:
                LOG.exception("* creating table or inserting data failed:")
                self.fail("error occurred during creating table and inserting data")

            #verify the data in the db before taking snapshots:
            self.verify_data(username, password, pub_ip)


        # NOW... take a snapshot
        # ----------------------
        body = r"""{ "snapshot": { "instanceId": """ + "\"" + self.instance_id + "\"" + ( r""", "name": "%s" } }""" % INSTANCE_NAME)
        resp, content = self._execute_request(client, "snapshots", "POST", body)
            
        # Assert 1) that the request was accepted and 2) that the response
        # is in the proper format.
        self.assertEqual(201, resp.status, ("Expected 201 as response to snapshot create but received %s" % resp.status))
        content = self._load_json(content,'Create Snapshot')
        self.assertTrue(content.has_key('snapshot'), "Did dnot receive 'snapshot' field in response to snapshot create")
        self.assertEqual(self.instance_id, content['snapshot']['instanceId'])

        self.snapshot_id = content['snapshot']['id']
        LOG.debug("Snapshot ID: %s" % self.snapshot_id)
        
        # Test listing all db snapshots.
        # ------------------------------
        LOG.info("* Listing all snapshots")
        resp, content = self._execute_request(client, "snapshots", "GET", "")

        # Assert 1) that the request was accepted and 2) that the response
        # is in the proper format.
        self.assertEqual(200, resp.status)
        content = self._load_json(content,'List all Snapshots')
        self.assertTrue(content.has_key('snapshots'))

        # Test listing all db snapshots for a specific instance.
        # ------------------------------------------------------
        LOG.info("* Listing all snapshots for %s" % self.instance_id)
        resp, content = self._execute_request(client, "snapshots?instanceId=" + self.instance_id , "GET", "")
        
        # Assert 1) that the request was accepted, 2) that the response
        # is in the proper format, and 3) that the list contains the created
        # snapshot.
        self.assertEqual(200, resp.status, ("Expected 200 response status to list snapshots for instance, but received %s" % resp.status))
        content = self._load_json(content,'List all Snapshots for Instance')
        self.assertTrue(content.has_key('snapshots'), "Expected 'snapshots' field in responst to list snapshots")
        found = False
        for each in content['snapshots']:
            if self.snapshot_id == each['id'] and \
               self.instance_id == each['instanceId']:
                found = True
        self.assertEqual(True, found)


        # Test getting details about a specific db snapshot.
        LOG.info("* Getting snapshot %s" % self.snapshot_id)
        resp, content = self._execute_request(client, "snapshots/" + self.snapshot_id , "GET", "")

        # Assert 1) that the request was accepted, 2) that the response
        # is in the proper format, and 3) that the response is the correct
        # snapshot.
        self.assertEqual(200, resp.status, "Expected 200 response status to list snapshots")
        content = self._load_json(content,'Get single Snapshot')
        self.assertTrue(content.has_key('snapshot'), "Response to list snapshots did not contain 'snapshot' field")
        self.assertEqual(self.instance_id, content['snapshot']['instanceId'])
        self.assertEqual(self.snapshot_id, content['snapshot']['id'])

        wait_so_far = 0
        status = content['snapshot']['status']
        while status != 'success':
            # wait a max of max_wait for snapshot status to show success
            time.sleep(10)
            wait_so_far += 10
            if wait_so_far >= MAX_WAIT_RUNNING:
                break

            resp, content = self._execute_request(client, "snapshots/" + self.snapshot_id , "GET", "")
            self.assertEqual(200, resp.status, ("Expected 200 response status to show snapshot, but received %s" % resp.status))
            content = json.loads(content)
            status = content['snapshot']['status']
            
        self.assertTrue(status == 'success', ("Snapshot %s did not switch to 'success' after waiting 5 minutes" % self.snapshot_id))

        # Test creating a new instance from a snapshot.
        # ---------------------------------------------
        LOG.info("* Creating instance from snapshot %s" % self.snapshot_id)
        snap_body = json.loads(instance_body)
        snap_body['instance']['snapshotId'] = self.snapshot_id
        snap_body = json.dumps(snap_body)

        resp, content = self._execute_request(client, "instances", "POST", snap_body)


        # Assert 1) that the request was accepted
        self.assertEqual(201, resp.status, "Expected 201 status to request to create instance from a snapshot ")       
        content = self._load_json(content,'Create Instance from Snapshot')

        credential = content['instance']['credential']

        self.instance_id = content['instance']['id']
        LOG.debug("create-from-snapshot Instance ID: %s" % self.instance_id)


        # Ensure the instance is up
        # -------------------------
        LOG.info("* Getting instance from snapshot %s" % self.instance_id)
        resp, content = self._execute_request(client, "instances/" + self.instance_id , "GET", "")
        self.assertEqual(200, resp.status, ("Expecting 200 response status to Instance Show but received %s" % resp.status))
        content = self._load_json(content,'Get Single Instance')

        wait_so_far = 0
        status = content['instance']['status']
        while status != 'running':
            # wait a max of max_wait for instance status to show running
            time.sleep(10)
            wait_so_far += 10
            if wait_so_far >= MAX_WAIT_RUNNING:
                break

            resp, content = self._execute_request(client, "instances/" + self.instance_id , "GET", "")
            self.assertEqual(200, resp.status, ("Expecting 200 response status to Instance Show but received %s" % resp.status))
            content = self._load_json(content,'Get Single Instance')
            status = content['instance']['status']

        if status != 'running':
            LOG.info("* instance is still not up after 5 minutes")
            self.fail("Instance %s did not go to running after boot and waiting 5 minutes" % self.instance_id)
        else :
            # verify customized data is inside the DB
            #LOG.info("* now verifying the customized data is inside the DB")
            pub_ip = content['instance']['hostname']
            username = credential['username']
            password = credential['password']
       #     db_name = 'food'
            self.verify_data(username, password, pub_ip)

#            time.sleep(20)
#            LOG.info("* connecting to mysql (instance boot from snapshot): %s, %s, %s" %(username, password, pub_ip))
#
#            try:
#                conn = MySQLdb.connect(host = pub_ip,
#                    user = username,
#                    passwd = password,
#                    db = db_name)
#                LOG.info("*")
#            except MySQLdb.Error as ex:
#                LOG.exception("* connecting to mysql (instance boot from snapshot) failed:")
#                self.fail("connecting to mysql failed (instance boot from snapshot) using pub ip %s" % pub_ip)
#
#            try:
#                LOG.info("* searching for fruit in the database: ")
#                cursor = conn.cursor()
#                cursor.execute("""
#                SELECT name FROM product
#                WHERE category = 'fruits'
#                """)
#
#                rows = cursor.fetchall()
#                for row in rows:
#                    if row is None or row[0] != "apple":
#                        LOG.info("* no fruits found in database")
#                        self.fail("instance does not have the customized data - fruits")
#                    else:
#                        LOG.info("* here comes %s" % row)
#
#                LOG.info("* searching for vegetable in db:")
#                cursor.execute("""
#                SELECT name FROM product
#                WHERE category = 'vegetables'
#                """)
#
#                rows = cursor.fetchall()
#                for row in rows:
#                    if ( row is None or
#                    (row[0] != 'tomato' and
#                     row[0] != 'broccoli')
#                    ) :
#                        LOG.info("* no veggie in db")
#                        self.fail("instance does not have the customized data - vegetables")
#                    else:
#                        LOG.info("* here comes %s" % row)
#            except MySQLdb.Error as ex:
#                LOG.exception("something is wrong in the db:")
#                self.fail("post snapshot verification failed on inconsistent data")

        # Test deleting a db snapshot.
        LOG.info("* Deleting snapshot %s" % self.snapshot_id)
        resp, content = self._execute_request(client, "snapshots/" + self.snapshot_id , "DELETE", "")

        # Assert 1) that the request was accepted and 2) that the snapshot
        # has been deleted.
        self.assertEqual(204, resp.status)

        resp, content = self._execute_request(client, "snapshots/" + self.snapshot_id , "GET", "")
        self.assertEqual(404, resp.status)
        
        time.sleep(10)

        # Finally, delete the instance.
        LOG.info("* Deleting instance %s" % self.instance_id)
        resp, content = self._execute_request(client, "instances/" + self.instance_id , "DELETE", "")

        # Assert 1) that the request was accepted and 2) that the instance has
        # been deleted.
        self.assertEqual(204, resp.status)

        resp, content = self._execute_request(client, "instances", "GET", "")
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
        client = httplib2.Http(".cache", disable_ssl_certificate_validation=True)

        # Get list of snapshots
        LOG.debug("- Getting list of snapshots")
        resp, snapshots = self._execute_request(client, "snapshots", "GET", "")
        snapshots = json.loads(snapshots)

        # Delete all orphaned instances and snapshots
        LOG.debug("- Deleting orphaned instances:")
        resp, content = self._execute_request(client, "instances", "GET", "")
        content = json.loads(content)

        for each in content['instances']:
#            LOG.debug("EACH: %s" % each)
            if each['name'] == INSTANCE_NAME:
                for snapshot in snapshots['snapshots']:
                    # If any snapshots belong to an instance to be deleted, delete the snapshots too
                    if snapshot['instanceId'] == each['id']:
                        LOG.debug("Deleting snapshot: %s" % snapshot['id'])
                        resp, content = self._execute_request(client, "snapshots/" + snapshot['id'], "DELETE", "")
                        LOG.debug(resp)
                        LOG.debug(content)                        
                LOG.debug("Deleting instance: %s" % each['id'])
                resp, content = self._execute_request(client, "instances/" + each['id'], "DELETE", "")
                LOG.debug(resp)
                LOG.debug(content)


    def _execute_request(self, client, path, method, body=None):
        resp, content = client.request(API_URL + path, method, body, AUTH_HEADER)
        LOG.debug(resp)
        LOG.debug(content)
        return resp,content


    def _attempt_telnet(self, instance_ip, telnet_port):
        success = False
        telnet = telnetlib.Telnet()
        try:
            LOG.debug("Attempting to telnet into %s" % instance_ip)
            telnet.open(instance_ip, telnet_port, 20)
            success = True
        except Exception, e:
            LOG.exception("Telnet Attempt Failed!")
        finally:
            telnet.close()
            
        return success

    def _ssh_and_execute(self, instance_ip, ssh_key, command):
        LOG.debug("- Attempting to SSH into %s" % instance_ip)
        
        if instance_ip is None:
            return None
        
        ssh_port_listening = False
        try:
            ssh_port_listening = self._attempt_telnet(instance_ip, 22)
        except Exception, e:
            self.fail("Telnet attempt to port 22 threw an exception")
        
        if ssh_port_listening is not True:
            raise Exception("Telnet attempt to port 22 Failed.  The box is not be ssh-able.")
        
        try:
            attempt = 0
            while attempt < 10:
                try:
                    LOG.debug("- SSH connection attempt %i" % attempt)
                    s = ssh.Connection(host = instance_ip, username = 'ubuntu', private_key = ssh_key)
                    
                    LOG.debug("- Executing command '%s'" % command)
                    result = s.execute(command)

                    LOG.debug("- Result: %s" % result)
                    return result
                except Exception, e:
                    #print e
                    pass

                attempt += 1
                time.sleep(4)
        except Exception, e:
            LOG.exception("Error connecting to instance")
        
        # If we get this far, then there is an issue
        raise Exception("Exhausted SSH attempts, and could not SSH onto box to determine cause of failure.  The box may not be ssh-able.")

    def _load_json(self, content, operation):
        try:
            content = json.loads(content)
        except Exception, e:
            LOG.exception("Error parsing response JSON")
            self.fail("Response to %s was not proper JSON: $s" % (operation,content))

        return content


    def verify_data(self, username, password, pub_ip):
    # verify customized data is inside the DB
        LOG.info("* now verifying the customized data is inside the DB")
        db_name = 'food'

        time.sleep(20)
        LOG.info("* connecting to mysql (instance boot from snapshot): %s, %s, %s" %(username, password, pub_ip))

        try:
            conn = MySQLdb.connect(host = pub_ip,
                user = username,
                passwd = password,
                db = db_name)
            LOG.info("*")
        except MySQLdb.Error as ex:
            LOG.exception("* connecting to mysql (instance boot from snapshot) failed:")
            self.fail("connecting to mysql failed (instance boot from snapshot) using pub ip %s" % pub_ip)

        try:
            LOG.info("* searching for fruit in the database: ")
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM product
                WHERE category = 'fruits'
                """)

            rows = cursor.fetchall()
            for row in rows:
                if row is None or row[0] != "apple":
                    LOG.info("* no fruits found in database")
                    self.fail("instance does not have the customized data - fruits")
                else:
                    LOG.info("* here comes %s" % row)

            LOG.info("* searching for vegetable in db:")
            cursor.execute("""
                SELECT name FROM product
                WHERE category = 'vegetables'
                """)

            rows = cursor.fetchall()
            for row in rows:
                if ( row is None or
                     (row[0] != 'tomato' and
                      row[0] != 'broccoli')
                    ) :
                    LOG.info("* no veggie in db")
                    self.fail("instance does not have the customized data - vegetables")
                else:
                    LOG.info("* here comes %s" % row)
        except MySQLdb.Error as ex:
            LOG.exception("something is wrong in the db:")
            self.fail("post snapshot verification failed on inconsistent data")