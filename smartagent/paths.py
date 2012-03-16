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
from os import environ

__author__ = 'dragosmanolescu'
__email__ = 'dragosm@hp.com'
__python_version__ = '2.7.2'

# Pull all file system paths here

backlog_path = '/home/nova/backup_logs/'
backup_path = '/var/lib/mysql-backup/'
smartagent_working_dir = '/home/nova'
mycnf_base = environ['HOME']
mysql_var_path = '/var/lib/mysql'
smartagent_name = 'smartagent'
smartagent_pid_file_name = 'service.pid'
smartagent_config_file_name = 'agent.config'
mysql_config_file = '.my.cnf'