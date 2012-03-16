# Copyright 2012 HP Software, LLC.
# All Rights Reserved.
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
import os
import time
import logging
import logging.handlers
from smart_agent import SmartAgent
import paths

__author__ = 'dragosmanolescu'
__email__ = 'dragosm@hp.com'
__python_version__ = '2.7.2'

class Service:
    def __init__(self,
                 working_directory=paths.smartagent_working_dir):
        self.working_directory = working_directory
        self.name = __name__
        self.logger = None
        self.pid_filename = None

    def setup(self):
        """
        Setup while running in the launcher's process
        """
        self.logger = logging.getLogger(paths.smartagent_name)
        self.logger.setLevel(logging.DEBUG)
        handler = logging.handlers.TimedRotatingFileHandler(
            # log file opened before daemon start
            filename=os.path.join(
                self.working_directory,
                __name__ + '.log'),
            when='d',
            interval=7,
            delay=True)  # ensure file won't be closed
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            "[%(process)d] %(asctime)s:%(levelname)s:%(name)s:%(message)s")
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def start(self):
        """
        Enter here when it is running in a different process than
        the launcher
        """
        pid = os.getpid()
        self.logger.debug('daemon running')
        self.pid_filename = os.path.join(self.working_directory,
            paths.smartagent_pid_file_name)
        try:
            with open(self.pid_filename, 'w') as pid_file:
                pid_file.writelines(str(pid))
        except IOError as io_error:
            self.logger.error('Error creating PID file %s', self.pid_filename)
        else:
            self.logger.debug('Daemon PID written to %s', self.pid_filename)
        smart_agent = SmartAgent(logger=self.logger)
        smart_agent.run()

    def shutdown(self, signal_number, stack_frame):
        self.logger.debug('Shutting down')
        if self.pid_filename is not None:
            os.remove(self.pid_filename)
            self.logger.debug('Daemon PID file removed')
        self.logger.flush()
        self.logger.close()

    def restart(self, signal_number, stack_frame):
        self.logger.debug('SIGHUP received')


if __name__ =='__main__':
    sa = Service()
    sa.setup()
    sa.start()
