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
import time
import os.path
import errno
import socket
import re
import subprocess
import paths
import logging

LOG = logging.getLogger(paths.smartagent_name)

class MySqlChecker:
    """
    Make a given number of attempts to determine whether a MySQL instance is
    up an running on the given host
    """
    def __init__(self,
                 host_name='127.0.0.1',
                 port_number=3306,
                 pid_file_path=paths.mysql_var_path):
        self.host_name = host_name
        self.port_number = port_number
        self.pid_file_path = pid_file_path

    def _get_pid(self):
        """
        Extracts PID string from .pid file, or None if the file
        doesn't exist/cannot be read
        """
        pid_file_name = os.path.join(self.pid_file_path, os.uname()[1])\
            + '.pid'
        LOG.debug('Checking pid file %s', pid_file_name)
        try:
            with open(pid_file_name, 'r') as pid_file:
                pid_string = pid_file.read().rstrip('\n')
                LOG.debug('pid file read: %s', pid_string)
        except IOError as io_exception:
            LOG.debug('Exception caught while opening PID file; %s',
                str(io_exception))
            return self._findPid('mysqld')
        else:
            return pid_string

    def _findPid(self, proc_name):
        """
        This method is a fallback for obtaining mysqld's PID when the
        .pid file cannot be read
        """
        ps = subprocess.Popen("ps ax -o pid= -o state= -o command=", shell=True, stdout=subprocess.PIPE)
        ps_pid = ps.pid
        output = ps.stdout.read()
        ps.stdout.close()
        ps.wait()
        for line in output.split("\n"):
            res = re.findall("(\d+) ([^ZT]\w?) (.*)", line)
            if res:
                pid = int(res[0][0])
                if proc_name in res[0][2] and pid != os.getpid() and pid != ps_pid:
                    return pid
        return None

    def _is_process_alive(self, pid_string):
        """
        Verifies whether the process is alive:
        - First kill -0
        - If that fails (no permission) then from the /proc filesystem
        """
        try:
            os.kill(int(pid_string), 0)  # send null signal
        except OSError as err:
            if err.errno == errno.ESRCH:
                LOG.debug('Process %s doesn''t exist:', pid_string)
                return False
            elif err.errno == errno.EPERM:
                LOG.debug('Operation not permitted on process %s',
                    pid_string)
                if not os.path.isdir('/proc'):
                    LOG.debug('/proc filesystem doesn''t exist')
                    return False
                proc_pid_file = os.path.join('/proc',
                    pid_string,
                    'status')
                LOG.debug('Checking /proc file %s', proc_pid_file)
                return os.path.exists(proc_pid_file)
            else:
                LOG.error('Unknown error while checking \
                    process state: %s', str(sys.exc_info()[0]))
        else:
            LOG.debug('Process %s responded to null signal', pid_string)
            return True

    def check_once_if_running(self):
        """
        Checks if mysqld is running:
        - First look for the pid file (distribution-dependent; default
        value for ubuntu)
        - Next send the null signal to check if the process is running
        (same as in the mysql.server script)
        - Finally open the socket and look for the version number in the
         protocol handshake string
        """

        pid_string = self._get_pid()
        if pid_string is None:
            return False
        if not self._is_process_alive(pid_string):
            return False
        try:
            mysql_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            mysql_socket.connect((self.host_name, self.port_number))
            response = mysql_socket.recv(4096)
            LOG.debug('mysqld protocol response: %s', response)
        except Exception:
            LOG.error('Error connecting to mysqld on %s:%d: %s',
                self.host_name,
                self.port_number,
                str(sys.exc_info()[0]))
            return False
        else:
            mysql_socket.close()
            LOG.debug('Looking for MySQL protocol version 5.X.X')
            # TODO: MySQL protocol version-dependent
            regex = re.compile('5.[0-9]+.[0-9]+')
            matches = regex.findall(response)  # http://www.pythonregex.com/
            return len(matches) > 0

    def check_if_running(self, sleep_time_seconds=5, number_of_checks=10):
        """
        Performs number_of_checks, waiting sleep_time_seconds between them.
        Upon receiving True from isRunning it returns True; if that hasn't
        happened after the given number of checks returns False
        """
        iteration = 0
        try:
            while iteration < number_of_checks:
                LOG.debug('Checking iteration %d' % iteration)
                if self.check_once_if_running():
                    return True
                else:
                    time.sleep(sleep_time_seconds)
                    iteration = iteration + 1
            return False
        except Exception:
            LOG.error('Exception while iterating, aborting: %s',
                str(sys.exc_info()[0]))
            raise


def main():
    platform = os.uname()[3].lower()
    if platform.find('ubuntu') > -1:
        print 'Running on Linux'
        checker = MySqlChecker()
        # using defaults
    elif platform.find('darwin') > -1:
        print 'Running on OS X'
        checker = MySqlChecker(pid_file_path='/usr/local/var/mysql')
    else:
        print 'Unsupported platform?'
        sys.exit(-1)

    if checker.check_if_running(5, 7):
        # send phone home message
        print 'MySQL is running'
    else:
        print 'MySQL is not running'
        # send message signaling that MySQL is not running
    sys.exit(0)

if __name__ == '__main__':
    main()
