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

def create_boot_config(configuration_manager, credential, storage_uri, password):
    """Creates a config file that gets placed in the instance
    for the Agent to configure itself"""

    rabbit_config = "[messaging]\nrabbit_host: {host}\nrabbit_port: {port}\nrabbit_use_ssl: {ssl}\nrabbit_user_id: {user}\nrabbit_password: {password}\nrabbit_virtual_host: {vhost}\n".format(
        host=configuration_manager.get('rabbit_host', 'localhost'),
        port=configuration_manager.get('rabbit_port', '5672'),
        ssl=configuration_manager.get('rabbit_use_ssl', 'False'),
        user=configuration_manager.get('rabbit_userid', 'user'),
        password=configuration_manager.get('rabbit_password', 'password'),
        vhost=configuration_manager.get('rabbit_virtual_host', '/')
    )

    configuration = "{rabbit}\n[database]\ninitial_password: {dbpassword}\n".format(rabbit=rabbit_config, dbpassword=password)

    if storage_uri and len(storage_uri) > 0:
        configuration = "{config}\n[snapshot]\nsnapshot_uri: {uri}\nswift_auth_url: {auth_url}\nswift_auth_user: {tenantid}:{username}\nswift_auth_key: {auth_key}\n".format(
            config=configuration,
            uri=storage_uri,
            auth_url=configuration_manager.get('reddwarf_proxy_swift_auth_url', 'http://0.0.0.0:5000/v2.0'),
            tenantid=credential['tenant_id'],
            username=credential['user_name'],
            auth_key=credential['password']
        )
    return configuration