#!/usr/bin/python

# Copyright 2012 HP Software, LLC
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

__author__ = 'dragosmanolescu'
__email__ = 'dragosm@hp.com'
__python_version__ = '2.7.2'

import sys
import daemon
import _mysql  # see http://mysql-python.sourceforge.net/MySQLdb.html
from singleton import Singleton
import logging

@Singleton
class DatabaseManager:
    """
    This class encapsulates a (singleton) connection to a database.
    """
    def __init__(self,
                 host_name='localhost',
                 database_name='mysql',
                 config_file='.my.cnf',
                 logger=logging.getLogger(__name__)):
        self.logger = logger
        self.host_name = host_name
        self.database_name = database_name
        self.config_file = config_file
        self._database_connection = None

    def __del__(self):
        self.close_connection()

    def open_connection(self):
        if self._database_connection:
            self.logger.debug("Database connection already opened")
            return  # already connected
        try:
            self.logger.debug('Connecting to database')
            connection = _mysql.connect(host=self.host_name,
                db=self.database_name,
                read_default_file=self.config_file)
        except Exception as ex:
            self.logger.error('Error connecting to the database: %s', ex)
        else:
            self._database_connection = connection
        return

    def close_connection(self):
        if self._database_connection:
            try:
                self._database_connection.close()
            except Exception as ex:
                self.logger.error('Error closing database connection: %s',
                    ex)
                return False
            else:
                return True
        return False

    def status(self):
        if not self._database_connection:
            self.open_connection()
        if self._database_connection:
            return self._database_connection.stat()
        else:
            return ''

    def execute_sql_commands(self,
                             commands):
        assert self._database_connection
        try:
            for command in commands:
                self._database_connection.query(command)
        except Exception as ex:
            self.logger.error('Database error while executing %s: %s',
                command, ex)
            return False
        else:
            return True

def main():
    """ main program """
    logging.basicConfig(level=logging.DEBUG)
    persistence_agent = DatabaseManager(host_name='localhost',
        database_name='information_schema',
        config_file='~/.my.cnf')
    if persistence_agent.open_connection():
        print "Database connected"

    print persistence_agent.status()

if __name__ == '__main__':
    main()
