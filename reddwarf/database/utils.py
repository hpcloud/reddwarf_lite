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

import re

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
                   'rabbit_virtual_host': '/',
                   'amqp_connection_uri': None }
    
    section = 'messaging'
    config.add_section(section) 
    for k in rabbit_dict.keys():
        v = configuration_manager.get(k, rabbit_dict[k])
        if v:
          config.set(section, k, v)

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

def file_dict_as_userdata(file_dict, default_chown="nova:mysql", default_chmod="644"):
    """Workaround for unreliable KVM-based file injection; stuff the files in
       a user-data script that will manually cat them back out.  The horror. """

    result = "#!/bin/sh\n"
    for (filename, file_info) in file_dict.items():
        if type(file_info) == type(""):
            file_info = {"contents": file_info}
        result += """cat >%s <<EOS
%s
EOS\n
""" % (filename, file_info.get('contents'))
        result += "chown %s %s\n" % (file_info.get('chown', default_chown), filename)
        result += "chmod %s %s\n" % (file_info.get('chmod', default_chmod), filename)

    return result

class Sanitizer():
    
    def _init__(self):
        pass
    
    def whitelist_uuid(self, input, default_accept=False):
        whitelist = re.compile("[A-Za-z0-9]{8}-[A-Za-z0-9]{4}-[A-Za-z0-9]{4}-[A-Za-z0-9]{4}-[A-Za-z0-9]{12}")
        match = whitelist.match(input)
        
        if match and input == match.group():
            default_accept = True
        
        return default_accept
        
        