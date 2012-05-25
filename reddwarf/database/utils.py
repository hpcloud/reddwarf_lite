# Copyright 2012 HP Software, LLC
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

import ConfigParser
import StringIO

def create_boot_config(configuration_manager, credential, storage_uri, password):
    """Creates a config file that gets placed in the instance
    for the Agent to configure itself"""

    config = ConfigParser.SafeConfigParser()
    
    rabbit_dict = {'rabbit_host': 'localhost', 
                   'rabbit_port': '5672', 
                   'rabbit_use_ssl': 'False',
                   'rabbit_userid': 'user',
                   'rabbit_password': 'password',
                   'rabbit_virtual_host': '/'}
    
    section = 'messaging'
    config.add_section(section) 
    for each in rabbit_dict.keys():
        config.set(section, each, configuration_manager.get(each, rabbit_dict[each]))

    section = 'database'
    config.add_section(section)
    config.set(section, 'initial_password', password)

    if storage_uri and len(storage_uri) > 0:
        section = 'snapshot'
        config.add_section(section)
        config.set(section, 'snapshot_uri', storage_uri)
        config.set(section, 'swift_auth_url', configuration_manager.get('reddwarf_proxy_swift_auth_url', 'http://0.0.0.0:5000/v2.0'))
        config.set(section, 'swift_auth_user', "%s:%s" % (credential['tenant_id'], credential['user_name']))
        config.set(section, 'swift_auth_key', credential['password'])
        config.set(section, 'snapshot_key', configuration_manager.get('snapshot_key',"changeme"))
    
    mem_file = StringIO.StringIO()
    config.write(mem_file)
    
    return mem_file.getvalue()
