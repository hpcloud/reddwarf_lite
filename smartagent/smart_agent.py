# Copyright 2012 HP Software, LLC
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import ConfigParser
import logging
import os
from subprocess import call
import time
import sys
from result_state import ResultState
from check_mysql_status import MySqlChecker
from command_handler import MysqlCommandHandler
from smartagent_messaging import MessagingService
import paths

__author__ = 'dragosmanolescu'
__email__ = 'dragosm@hp.com'
__python_version__ = '2.7.2'

AGENT_HOME = paths.smartagent_working_dir
AGENT_CONFIG = os.path.join(AGENT_HOME, paths.smartagent_config_file_name)

class SmartAgent:
    def __init__(self, logger=None):
        # logging
        if logger is None:
            self.logger = logging.getLogger(paths.smartagent_name)
            logging.basicConfig(level=logging.DEBUG,
                format='%(asctime)s %(levelname)8s %(message)s')
        else:
            self.logger = logger
        # messaging
        mq_conf = self._load_config("messaging")
        if not mq_conf:
            self.messaging = MessagingService() # using default MQ host
        else:
            self.messaging = MessagingService(host_address=mq_conf['rabbit_host'])
        self.messaging.callback = self.process_message
        # others
        self.handler = MysqlCommandHandler()
        # get snapshot config if any
        self.snapshot_conf = self._load_config("snapshot") #TODO: hardcoded name
        self.agent_username = 'os_admin' #TODO: hardcoded name
        self.test_username = 'dbas' #TODO: it needs to be passed from API Server

    def _load_config(self, section):
        result = {}
        config = ConfigParser.ConfigParser()
        config.read(AGENT_CONFIG)
        try:
            options = config.options(section)
        except Exception:
            return None
        for option in options:
            try:
                result[option] = config.get(section, option)
            except Exception:
                result[option] = None
        return result

    def _get_mysql_status(self):
        """ This calls the method to check MySQL's running status """
        if self.handler.is_mysql_running():
            return str(ResultState.RUNNING)
        else:
            return str(ResultState.NOSTATE)

    def run(self):
        """ Run the smart agent """
        if not self.snapshot_conf:
            # initial check for DB status and phone home to API Server

            hostname = os.uname()[1]
            message = {"method": "update_instance_state",
                       "args": {'hostname': hostname,
                                'state': self._get_mysql_status()
                       }}
            try:
                self.messaging.phone_home(message)
                self.logger.debug('Initial DB status checked and phone home message sent: %s', message)
            except Exception as err:
                self.logger.error("Failed to connect to MQ due to channel not available: %s", err)
        else:
            # apply snapshot if the instance is configured to do so
            result = self.handler.apply_db_snapshot(self.snapshot_conf['snapshot_uri'],
                self.snapshot_conf['swift_auth_user'],
                self.snapshot_conf['swift_auth_key'],
                self.snapshot_conf['swift_auth_url'])
            try:
                self.messaging.phone_home(result)
                self.logger.debug('Initial snapshot applied and phone home message sent: %s', result)
            except Exception as err:
                self.logger.error("Failed to connect to MQ due to channel not available: %s", err)
        # start listening and consuming rpc messages from API Server
        listen = True
        while listen:
            try:
                self.messaging.start_consuming()
            except OSError as os_error:  # killed by launcher
                self.logger.debug("OSError caught, leaving start_consuming")
                listen = False
            except Exception as err:
                self.logger.fatal("Error processing RPC request; last error: %s",
                    str(sys.exc_info()[0]))
                self.logger.error("Restarting start_consuming")
        return  # return upon being killed

    def create_database_instance(self, msg):
        """ This will call the method that creates a database instance"""
        self.logger.debug('Functionality not implemented')
        result = None
        return result

    def delete_database_instance(self, msg):
        """ This will call the method that deletes a database instance"""
        self.logger.debug('Functionality not implemented')
        result = None
        return result

    def create_database(self, msg):
        """ This calls the method that deletes a database schema"""
        database_name = msg['args']['database']
        if database_name:
            result = self.handler.create_database(database_name)
        else:
            self.logger.error('Missing database name in %s', str(msg['args']))
            result = ResultState.FAILED
        return result

    def restart_database(self, msg):
        """ This restarts MySQL for reading conf changes"""
        result = call("sudo service mysql restart", shell=True)
        return result

    def restart_database_instance(self, msg):
        """ This will call the method that restarts the database instance """
        self.logger.debug('Functionality not implemented')
        result = None
        return result

    def reset_password(self, msg):
        """ This calls the method that changes the user password """
        result = self.handler.reset_user_password(
            self.test_username, msg['args']['password'])
        return result

    def create_user(self, msg):
        """ This calls the method that creates a given database user """
        result = self.handler.create_user(
            msg['args']['username'],
            msg['args']['hostname'],
            msg['args']['password'])
        return result

    def delete_user(self, msg):
        """ This calls the method that deletes a database user """
        result = self.handler.delete_user(msg['args']['username'])
        return result

    def take_database_snapshot(self, msg):
        """ This will call the method that creates a database snapshot """
        result = self.handler.create_db_snapshot(msg['args']['sid'],
            msg['args']['credential']['user'],
            msg['args']['credential']['key'],
            msg['args']['credential']['auth'])
        self.messaging.phone_home(result)

    def apply_database_snapshot(self, msg):
        print "process touches here"

        result = self.handler.apply_db_snapshot(msg['args']['storage_path'],
            msg['args']['credential']['user'],
            msg['args']['credential']['key'],
            msg['args']['credential']['auth'])
        self.messaging.phone_home(result)

    def get_system_info(self):
        """ This calls the method to get system OS information """
        self.logger.debug('System info')
        hostname = os.uname()[1]
        unumber = os.getuid()
        pnumber = os.getpid()
        where = os.getcwd()
        what = os.uname()
        now = time.time()
        means = time.ctime(now)
        # TODO: assemble into string and inject in response
        self.logger.debug("Hostname: %s", hostname)
        self.logger.debug("User ID: %s", unumber)
        self.logger.debug("Process ID: %s", pnumber)
        self.logger.debug("Current Directory: %s", where)
        self.logger.debug("System information: %s", what)
        self.logger.debug("Time is now: %s", means)
        result = None
        return result

    def process_message(self, msg):
        """Performs actual agent work. Called by on_request() whenever
           a message is received, and calls the appropriate function based
           on the contents of the method key in the message.

           Arguments: self
           msg -- A dictionary representation of a JSON object
           Return type: A dictionary of {result of method execution,
           failure code (default for each is None)}"""

        result = None
        failure = None

        # will use this for reset agent password
        # agent_username = 'os_admin'

        # The following is a dispatcher
        # TODO: use pythonic solution with dictionary of methods
        # Make sure the method key is part of the JSON - if not, it's
        # invalid.
        # TODO: Return appropriate result/failure values (currently
        # None/None)
        try:
            method = msg['method']
        except KeyError:
            self.logger.error('Message missing "method" element: %s', msg)
            return {'result': result, 'failure': 'missing_method'}
        self.logger.debug ('Dispatching %s', method)
        # internal API
        if method == 'create_instance':
            result = self.create_database_instance(msg)
        elif method == 'delete_instance':
            result = self.delete_database_instance(msg)
        elif method == 'restart_instance':
            result = self.restart_database_instance(msg)
        elif method == 'restart_database':
            result = self.restart_database(msg)
        elif method == 'create_user':
            result = self.create_user(msg)
        elif method == 'delete_user':
            result = self.delete_user(msg)
        elif method == 'create_database':
            result = self.create_database(msg)
        elif method == 'reset_password':
            result = self.reset_password(msg)
        elif method == 'create_snapshot':
            result = self.take_database_snapshot(msg)
        elif method == 'apply_snapshot':
            result = self.apply_database_snapshot(msg)
        elif method == 'check_mysql_status':
            result = self._get_mysql_status()
        elif method == 'check_system_status':
            result = self.get_system_info()
        else:
            failure = 'unsupported_method'
        return {'result': result, 'failure': failure}
