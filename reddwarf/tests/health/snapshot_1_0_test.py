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
#(Snapshots)
#Create            X           X               X                 -
#Delete            X           X               -                 -
#Show              X           X               -                 -
#Show All          X           X               -                 -
#Apply             X           X               X                 -

from dbapi_test import DBFunctionalTests
from dbapi_test import DELAYS
from dbapi_test import LOG
from dbapi_test import INSTANCE_NAME
from dbapi_test import TIMEOUTS
from dbapi_test import TIMEOUT_STR
from dbapi_test import POLL_INTERVALS

import json
import time
import httplib2


class SnapshotTest(DBFunctionalTests):

    def tearDown(self):
        DBFunctionalTests.tearDown(self)

    def test_instance_api(self):
        """Override the super class method"""
        pass

    def _get_client(self):
        """Override the https protocol"""
        client = httplib2.Http(".cache", timeout=TIMEOUTS['https'],
                               disable_ssl_certificate_validation=True)
        return client

    #########################
    # helper methods
    #########################
    def _get_instance(self, client, instance_id):
        return self._execute_request(client,
                                     "instances/" + instance_id,
                                     "GET", "")

    def _get_instances(self, client):
        return self._execute_request(client,
                                     "instances",
                                     "GET", "")

    def _ensure_instance_active(self, client, credential):
        LOG.info("* Getting instance %s" % self.instance_id)
        resp, content = self._get_instance(client, self.instance_id)
        self.assertEqual(200, resp.status, (
            "Expecting 200 response status to Instance Show but received %s" %
            resp.status))
        content = self._load_json(content, 'Get Single Instance')
        wait_so_far = 0
        status = content['instance']['status']
        while status != 'running':
            # wait a max of max_wait for instance status to show running
            time.sleep(POLL_INTERVALS['boot'])
            wait_so_far += POLL_INTERVALS['boot']
            if wait_so_far >= TIMEOUTS['boot']:
                break

            resp, content = self._get_instance(client, self.instance_id)

            self.assertEqual(200, resp.status, (
                "Expecting 200 response status to Instance Show but received"
                " %s"
                % resp.status))
            content = self._load_json(content, 'Get Single Instance')
            status = content['instance']['status']
        if status != 'running':
            LOG.info("* instance is still not up after %s" % (TIMEOUT_STR))
            self.fail(
                "Instance %s did not go to running after boot and waiting "
                "%s" % (
                    self.instance_id, TIMEOUT_STR))
        else:
            # Add customized data to the database
            LOG.info("* Creating customized DB and inserting data")
            pub_ip = content['instance']['hostname']
            username = credential['username']
            password = credential['password']

            self.populate_data(username, password, pub_ip)

            #verify the data in the db before taking snapshots:
            self.verify_data(username, password, pub_ip)

    ###############################################
    # Create a DB instance for snapshot tests
    ###############################################
    def _create_db_instance(self):
        LOG.info("* Creating db instance")
        instance_body = r"""
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
        client = httplib2.Http(".cache", timeout=TIMEOUTS['http'],
                               disable_ssl_certificate_validation=True)

        resp, content = self._execute_request(client, "instances", "POST",
                                              instance_body)

        self.assertEqual(201, resp.status, (
            "Expecting 201 response status to Instance Create but received %s"
            % resp.status))

        content = self._load_json(content, 'Create Instance for Snapshotting')
        self.assertTrue(content.has_key('instance'),
                        "Response body of create instance does not contain "
                        "'instance' element")
        credential = content['instance']['credential']
        self.instance_id = content['instance']['id']

        LOG.debug("Instance ID: %s" % self.instance_id)

        #---------------------------------------------------------
        # Test creating a db snapshot immediately after creation.
        #---------------------------------------------------------
        LOG.info(
            "* Creating immediate snapshot for instance %s" % self.instance_id)
        body = r"""{ "snapshot": { "instanceId": """ + "\"" + self \
            .instance_id + "\"" + (r""", "name": "%s" } }""" % INSTANCE_NAME)
        resp, content = self._execute_request(client, "snapshots", "POST",
                                              body)

        #-----------------------------------------------
        # Assert 1) that the request was not accepted
        #-----------------------------------------------
        self.assertEqual(423, resp.status, ("Expected 423 to immediate "
                                            "snapshot creation, "
                                            "but received %s" % resp.status))

        #---------------------------
        # Ensure the instance is up
        #---------------------------
        self._ensure_instance_active(client, credential)

        return client, instance_body

    ###################################
    # NOW... take a snapshot
    ###################################
    def _take_snaphot(self, client):
        body = r"""{ "snapshot": { "instanceId": """ + "\"" + self \
            .instance_id + "\"" + (r""", "name": "%s" } }""" % INSTANCE_NAME)
        resp, content = self._execute_request(client, "snapshots", "POST",
                                              body)
        #------------------------------------------------------------------
        # Assert 1) that the request was accepted and 2) that the response
        # is in the proper format.
        #------------------------------------------------------------------
        self.assertEqual(201, resp.status, (
            "Expected 201 as response to snapshot create but received %s" %
            resp
            .status))
        content = self._load_json(content, 'Create Snapshot')
        self.assertTrue(content.has_key('snapshot'),
                        "Did dnot receive 'snapshot' field in response to "
                        "snapshot create")
        self.assertEqual(self.instance_id, content['snapshot']['instanceId'])
        self.snapshot_id = content['snapshot']['id']
        LOG.debug("Snapshot ID: %s" % self.snapshot_id)

        #--------------------------------
        # Test listing all db snapshots.
        # -------------------------------
        LOG.info("* Listing all snapshots")
        resp, content = self._execute_request(client, "snapshots", "GET", "")
        # Assert 1) that the request was accepted and 2) that the response
        # is in the proper format.
        self.assertEqual(200, resp.status)
        content = self._load_json(content, 'List all Snapshots')
        self.assertTrue(content.has_key('snapshots'))

        #---------------------------------------------------------
        # Test listing all db snapshots for a specific instance.
        #---------------------------------------------------------
        LOG.info("* Listing all snapshots for %s" % self.instance_id)
        resp, content = self._execute_request(client,
                                              "snapshots?instanceId=" + self
                                              .instance_id,
                                              "GET", "")
        #---------------------------------------------------------------------
        # Assert 1) that the request was accepted, 2) that the response
        # is in the proper format, and 3) that the list contains the created
        # snapshot.
        #---------------------------------------------------------------------
        self.assertEqual(200, resp.status, (
            "Expected 200 response status to list snapshots for instance, "
            "but received %s" % resp.status))
        content = self._load_json(content, 'List all Snapshots for Instance')
        self.assertTrue(content.has_key('snapshots'),
                        "Expected 'snapshots' field in responst to list "
                        "snapshots")
        found = False
        for each in content['snapshots']:
            if self.snapshot_id == each['id'] and self.instance_id == each['instanceId']:
                found = True
        self.assertEqual(True, found)

        #-----------------------------------------------------
        # Test getting details about a specific db snapshot.
        #-----------------------------------------------------
        LOG.info("* Getting snapshot %s" % self.snapshot_id)
        resp, content = self._execute_request(client,
                                              "snapshots/" + self.snapshot_id,
                                              "GET", "")
        #------------------------------------------------------------------
        # Assert 1) that the request was accepted,
        #        2) that the response is in the proper format, and
        #        3) that the response is the correct snapshot.
        #------------------------------------------------------------------
        self.assertEqual(200, resp.status,
                         "Expected 200 response status to list snapshots")
        content = self._load_json(content, 'Get single Snapshot')
        self.assertTrue(content.has_key('snapshot'),
                        "Response to list snapshots did not contain "
                        "'snapshot' field")
        self.assertEqual(self.instance_id, content['snapshot']['instanceId'])
        self.assertEqual(self.snapshot_id, content['snapshot']['id'])

        wait_so_far = 0
        status = content['snapshot']['status']
        while status != 'success':
            # wait a max of max_wait for snapshot status to show success
            time.sleep(POLL_INTERVALS['snapshot'])
            wait_so_far += POLL_INTERVALS['snapshot']
            if wait_so_far >= TIMEOUTS['boot']:
                break

            resp, content = self._execute_request(client,
                                                  "snapshots/" + self
                                                  .snapshot_id,
                                                  "GET", "")
            self.assertEqual(200, resp.status, (
                "Expected 200 response status to show snapshot, "
                "but received %s" % resp.status))
            content = json.loads(content)
            status = content['snapshot']['status']

        self.assertTrue(status == 'success', (
            "Snapshot %s did not switch to 'success' after waiting %s" %
            (self.snapshot_id, TIMEOUT_STR)))

    #######################################################################
    # test the entire snapshot 'life-cycle'
    #######################################################################
    def _create_db_instance_from_snapshot(self, client, instance_body):

        #-----------------------------------------------
        # Test creating a new instance from a snapshot.
        #-----------------------------------------------
        LOG.info("* Creating instance from snapshot %s" % self.snapshot_id)
        snap_body = json.loads(instance_body)
        snap_body['instance']['snapshotId'] = self.snapshot_id
        snap_body = json.dumps(snap_body)
        resp, content = self._execute_request(client, "instances", "POST",
                                              snap_body)

        #------------------------------------------
        # Assert 1) that the request was accepted
        #------------------------------------------
        self.assertEqual(201, resp.status,
                         "Expected 201 status to request to create instance "
                         "from a snapshot ")
        content = self._load_json(content, 'Create Instance from Snapshot')
        credential = content['instance']['credential']
        self.instance_id = content['instance']['id']
        LOG.debug("create-from-snapshot Instance ID: %s" % self.instance_id)

        #---------------------------
        # Ensure the instance is up
        # --------------------------
        LOG.info("* Getting instance from snapshot %s" % self.instance_id)
        resp, content = self._get_instance(client, self.instance_id)

        self.assertEqual(200, resp.status, (
            "Expecting 200 response status to Instance Show but received %s" %
            resp.status))
        content = self._load_json(content, 'Get Single Instance')
        wait_so_far = 0
        status = content['instance']['status']
        while status != 'running':
            # wait a max of max_wait for instance status to show running
            time.sleep(POLL_INTERVALS['boot'])
            wait_so_far += POLL_INTERVALS['boot']
            if wait_so_far >= TIMEOUTS['boot']:
                break

            resp, content = self._get_instance(client, self.instance_id)

            self.assertEqual(200, resp.status, (
                "Expecting 200 response status to Instance Show but received"
                " %s"
                % resp.status))
            content = self._load_json(content, 'Get Single Instance')
            status = content['instance']['status']
        if status != 'running':
            LOG.info("* instance is still not up after %s" % (TIMEOUT_STR))
            self.fail(
                "Instance %s did not go to running after boot and waiting "
                "%s" % (
                    self.instance_id, TIMEOUT_STR))
        else:
            # verify customized data is inside the DB
            #LOG.info("* now verifying the customized data is inside the DB")
            pub_ip = content['instance']['hostname']
            username = credential['username']
            password = credential['password']
            #     db_name = 'food'
            self.verify_data(username, password, pub_ip)

        #----------------------------------------------
        # Test deleting a db snapshot.
        #----------------------------------------------
        LOG.info("* Deleting snapshot %s" % self.snapshot_id)
        resp, content = self._execute_request(client,
                                              "snapshots/" + self.snapshot_id,
                                              "DELETE", "")
        #------------------------------------------------------------------
        # Assert 1) that the request was accepted and
        #        2) that the snapshot has been deleted.
        #------------------------------------------------------------------
        self.assertEqual(204, resp.status)
        resp, content = self._execute_request(client,
                                              "snapshots/" + self.snapshot_id,
                                              "GET", "")
        self.assertEqual(404, resp.status)
        time.sleep(DELAYS['after_delete'])
        # Finally, delete the instance.
        LOG.info("* Deleting instance %s" % self.instance_id)
        resp, content = self._execute_request(client,
                                              "instances/" + self.instance_id,
                                              "DELETE", "")
        #---------------------------------------------------------------------
        # Assert 1) that the request was accepted and
        #        2) that the instance has been deleted.
        #---------------------------------------------------------------------
        self.assertEqual(204, resp.status)
        resp, content = self._get_instances(client)

        try:
            content = json.loads(content)
        except Exception, err:
            LOG.error(err)
            LOG.error(
                "Deleting instance used for snapshots - "
                "Error processing JSON object: %s" % content)
            self.assertEqual(True, False)
        LOG.debug(content)
        for each in content['instances']:
            self.assertFalse(each['id'] == self.instance_id)

    #####################################################################
    # snapshot health test
    #####################################################################
    def test_snapshot_api(self):
        """Comprehensive snapshot API test using a snapshot lifecycle."""

        # 1.
        client, instance_body = self._create_db_instance()

        # 2.
        self._take_snaphot(client)

        # 3.
        self._create_db_instance_from_snapshot(client, instance_body)