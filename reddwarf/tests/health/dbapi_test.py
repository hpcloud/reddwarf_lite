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

AUTH_URL = r'''%s/tokens''' % (os.environ['OS_AUTH_URL'])
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

logging.basicConfig(format='%(levelname)-8s [%(asctime)s] %(name)s: %(message)s', level=logging.DEBUG)
LOG = logging.getLogger(__name__)

LOG.debug("Response from Keystone: %s" % content)
LOG.debug("Using Auth-Token %s" % AUTH_TOKEN)
LOG.debug("Using Auth-Header %s" % AUTH_HEADER)

UUID_PATTERN = '[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}'

BUILD_NUMBER = os.environ.get('BUILD_NUMBER', '')
INSTANCE_NAME = 'dbapi_health_%s_%s' % (BUILD_NUMBER, utils.generate_uuid())

TIMEOUTS = {
    'https': 270,
    'http': 270,
    'boot': 900,
    'mysql_connect': 300
}

POLL_INTERVALS = {
    'boot': 10,
    'snapshot': 10,
    'mysql_connect': 10,
    'ssh': 4
}

DELAYS = {
    'between_reset_and_restart': 30,
    'between_reboot_and_connect': 20,
    'after_delete': 10
}

TIMEOUT_STR="%.2f minutes" % (TIMEOUTS['boot']/60.0)

class DBFunctionalTests(unittest.TestCase):

    def test_instance_api(self):
        """Comprehensive instance API test using an instance lifecycle."""

        # Test creating a db instance.
        # ----------------------------
        LOG.info("* Creating db instance")
        body = r"""
        {"instance": {
            "name": "%s",
            "flavorRef": "103",
            "port": "3306",
            "dbtype": {
                "name": "mysql",
                "version": "5.5"
                }
            }
        }""" % INSTANCE_NAME

        client = httplib2.Http(".cache", timeout=TIMEOUTS['http'], disable_ssl_certificate_validation=True)
        resp, content = self._execute_request(client, "instances", "POST", body)

        # Assert 1) that the request was accepted and 2) that the response
        # is in the expected format.
        self.assertEqual(201, resp.status, ("Expecting 201 as response status of create instance but received %s" % resp.status))
        content = self._load_json(content,'Create Instance')
        self.assertTrue(content.has_key('instance'), "Response body of create instance does not have 'instance' field")

        credential = content['instance']['credential']

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
        pub_ip = content['instance']['hostname']
        while status != 'running' or pub_ip is None or len(pub_ip) <= 0:
            # wait a max of max_wait for instance status to show running
            time.sleep(POLL_INTERVALS['boot'])
            wait_so_far += POLL_INTERVALS['boot']
            if wait_so_far >= TIMEOUTS['boot']:
                break
            
            resp, content = self._execute_request(client, "instances/" + self.instance_id, "GET", "")
            self.assertEqual(200, resp.status, ("Expecting 200 as response status of show instance but received %s" % resp.status))
            content = self._load_json(content,'Get Single Instance')
            status = content['instance']['status']
            pub_ip = content['instance']['hostname']

        if status != 'running':

            self.fail("for some reason the instance did not switch to 'running' in %s" % TIMEOUT_STR)
        else:
            # try to connect to mysql instance
            pub_ip = content['instance']['hostname']
            # user/pass = credentials
            db_user = credential['username']
            db_passwd = credential['password']
            db_name = 'mysql'

            LOG.info("* Trying to connect to mysql DB on first boot: %s, %s, %s" %(db_user, db_passwd, pub_ip))
            conn = self.db_connect(db_user, db_passwd, pub_ip, db_name)
            if conn is None:
                self.fail("* maximum trials reached, db connection failed on first boot over %s: " % pub_ip)
            conn.close()



        # Test resetting the password on a db instance.
        # ---------------------------------------------
        LOG.info("* Resetting password on instance %s" % self.instance_id)
        resp, content = self._execute_request(client, "instances/" + self.instance_id +"/resetpassword", "POST", "")
        self.assertEqual(200, resp.status, ("Expecting 200 as response status of reset password but received %s" % resp.status))
        content = self._load_json(content,'Get new password')

        if resp.status == 200 :
            db_new_passwd = content['password']
            LOG.info("* Trying to connect to mysql DB after resetting password: %s, %s, %s" %(db_user, db_new_passwd, pub_ip))
            conn = self.db_connect(db_user, db_new_passwd, pub_ip, db_name)
            if conn is None:
                LOG.exception("* something is wrong with mysql connection after resetting password")
                conn.close()
                LOG.info("* Maybe the old password still works ?")
                conn_2 = self.db_connect(db_user, db_passwd, pub_ip, db_name)
                if conn_2 is None:
                    LOG.exception("* no, old password does not work anymore")
                else:
                    LOG.info("* old password still works, new password has not kicked in")
                conn_2.close()
                self.fail("* maximum trials reached, db connection failed after resetting password over %s: " % pub_ip)


        # XXX: Suspect restarting too soon after a "reset password" command is putting the instance in a bad mood on restart
        time.sleep(DELAYS['between_reset_and_restart'])

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
            time.sleep(POLL_INTERVALS['boot'])
            wait_so_far += POLL_INTERVALS['boot']
            if wait_so_far >= TIMEOUTS['boot']:
                break
            
            resp, content = self._execute_request(client, "instances/" + self.instance_id , "GET", "")
            self.assertEqual(200, resp.status, ("Expecting 200 as response status of show instance but received %s" % resp.status))
            content = self._load_json(content,'Get Single Instance')
            status = content['instance']['status']

        if status != 'running':
            self.fail("Instance %s did not go to running after a reboot and waiting %s" % (self.instance_id, TIMEOUT_STR))
        else:
            # try to connect to mysql instance
            time.sleep(DELAYS['between_reboot_and_connect'])
            LOG.info("* Trying to connect to mysql DB after rebooting the instance: %s, %s, %s" %(db_user, db_new_passwd, pub_ip))

            conn = self.db_connect(db_user, db_new_passwd, pub_ip, db_name)
            if conn is None:
                self.fail("* maximum trials reached, db connection failed after rebooting instance over %s: " % pub_ip)
            conn.close()

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
        time.sleep(DELAYS['after_delete'])

    def tearDown(self):
        """Run a clean-up check to catch orphaned instances/snapshots due to
           premature test failures."""

        LOG.debug("\n*** Starting cleanup...")
        client = self._get_client()

        # Get list of snapshots
        #LOG.debug("- Getting list of snapshots")
        #resp, snapshots = self._execute_request(client, "snapshots", "GET", "")
        #snapshots = json.loads(snapshots)

        # Delete all orphaned instances and snapshots
        LOG.debug("- Deleting orphaned instances:")
        resp, content = self._execute_request(client, "instances", "GET", "")
        content = json.loads(content)

        for each in content['instances']:
#            LOG.debug("EACH: %s" % each)
            if each['name'] == INSTANCE_NAME:
                #for snapshot in snapshots['snapshots']:
                 #   # If any snapshots belong to an instance to be deleted, delete the snapshots too
                 #   if snapshot['instanceId'] == each['id']:
                 #       LOG.debug("Deleting snapshot: %s" % snapshot['id'])
                 #       resp, content = self._execute_request(client, "snapshots/" + snapshot['id'], "DELETE", "")
                 #       LOG.debug(resp)
                 #       LOG.debug(content)
                LOG.debug("Deleting instance: %s" % each['id'])
                resp, content = self._execute_request(client, "instances/" + each['id'], "DELETE", "")
                LOG.debug(resp)
                LOG.debug(content)

    def _get_client(self):
        client = httplib2.Http(".cache", timeout=TIMEOUTS['http'],
                               disable_ssl_certificate_validation=True)
        return client

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
                time.sleep(POLL_INTERVALS['ssh'])
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

    def populate_data(self, username, password, pub_ip):
        db_name = 'mysql'

        LOG.info("* Connecting to mysql to add customized data: %s, %s, %s" %(username, password, pub_ip))

        conn = self.db_connect(username, password, pub_ip, db_name)
        if conn is None:
            self.fail("* maximum trials reached, db connection failed over %s: " % pub_ip)

        try:
            db_name = 'food'
            LOG.info("* Creating database %s" % db_name)
            cursor = conn.cursor()
            cursor.execute("CREATE DATABASE IF NOT EXISTS food")
            LOG.info("* database %s created" % db_name)
        except MySQLdb.Error as ex:
            LOG.exception("* creating database %s failed" % db_name)
            conn.close()
            self.fail("creating database food encounters error")

        try:
            LOG.info("* switching to the new database")
            cursor.execute("""
                    use food
                    """)
            LOG.info("* switched to use database %s" % db_name)
            LOG.info("* creating table")
            cursor.execute ("DROP TABLE IF EXISTS produce")
            cursor.execute("""
                    CREATE TABLE produce
                    (
                      name    CHAR(40),
                      category CHAR(40)
                    )
                    """)
            LOG.info("* table produce created")
            LOG.info("* inserting data into table")
            cursor.execute("""
                    INSERT INTO produce (name, category)
                    VALUES
                        ('apple', 'fruits'),
                        ('tomato', 'vegetables'),
                        ('broccoli', 'vegetables')
                    """)
            LOG.info("* Number of rows inserted: %d" %cursor.rowcount)
            cursor.execute("""
                        SELECT * FROM produce
                    """)
            LOG.info("* show table produce: %r" % repr(cursor.fetchall()))
            cursor.close()
            conn.commit()
        except MySQLdb.Error as ex:
            LOG.exception("* creating table or inserting data failed:")
            self.fail("error occurred during creating table and inserting data")
        finally:
            conn.close()

    def verify_data(self, username, password, pub_ip):
        # verify customized data is inside the DB
        LOG.info("* now verifying the customized data is inside the DB")
        db_name = 'food'

        LOG.info("* connecting to mysql database %s: %s, %s, %s" %(db_name, username, password, pub_ip))

        conn = self.db_connect(username, password, pub_ip, db_name)
        if conn is None:
            self.fail("* maximum trials reached, db connection failed over %s: " % pub_ip)

        try:
            LOG.info("* searching for fruit in the database: ")
            cursor = conn.cursor(MySQLdb.cursors.DictCursor)

            cursor.execute ("SELECT name, category FROM produce")

            result_set = cursor.fetchall()
            for row in result_set:
                if row['category'] == 'fruits':
                    if row['name'] != 'apple':
                        self.fail("data inconsistency: %s" % row['name'])
                    else:
                        LOG.info("found fruit %s" % row['name'])
                elif row['category'] == 'vegetables':
                    if row['name'] != 'tomato' and row['name'] != 'broccoli':
                        self.fail("data inconsistency: %s" % row['name'])
                    else:
                        LOG.info("found veggie: %s" % row['name'])
                else:
                    self.fail("data inconsistency: %s" % row['name'])
            cursor.close()
        except MySQLdb.Error as ex:
            LOG.exception("something wrong during verifying data:")
            self.fail("failed to verify data in DB, check log for details")
        finally:
            conn.close()

    def db_connect(self, username, password, hostname, db_name):
        trial_count = 1
        poll_interval = POLL_INTERVALS['mysql_connect']
        timeout = TIMEOUTS['mysql_connect']
        now = time.time()
        end = now + timeout
        while now < end:
            try:
                log_info = (trial_count, username, password, hostname, db_name)
                LOG.info("* db connection trial # %d: %s, %s, %s, %s" % log_info)
                connection = MySQLdb.connect(
                    host = hostname,
                    user = username,
                    passwd = password,
                    db = db_name)
                LOG.info("* connection established, returning connection object")
                return connection
            except MySQLdb.Error as ex:
                trial_count += 1
                LOG.debug("* db seems not ready for socket connection, sleep for %ds" % poll_interval)
            time.sleep(poll_interval)
            now = time.time()
        # We've fallen through at this point
        LOG.error("* timed out trying to connect to database after %ss and %d attempts", timeout, trial_count)
        return None
