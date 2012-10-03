# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2010-2012 OpenStack LLC.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http: //www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.


import os

class FlavorView(object):

    def __init__(self, flavor, tenant_id, request=None):
        self.flavor = flavor
        self.tenant_id = tenant_id
        self.request = request

    def show(self):
        return {
            "flavor": {
                'id': int(self.flavor['flavor_id']),
                'links': self._build_links(),
                'name': self.flavor['flavor_name'],
                'ram': self.flavor['ram'],
                'vcpu': self.flavor['vcpus'],
            }
        }     

    def _build_links(self):
        """Build the links for the flavor information."""
        base_url = self.request.application_url
        href = os.path.join(base_url, self.tenant_id,
                            "flavors", str(self.flavor['flavor_id']))
        links= [
            {
                'rel': 'self',
                'href': href
            }
        ]
        return links


class FlavorsView(object):
    view = FlavorView

    def __init__(self, flavors, tenant_id, request=None):
        self.flavors = flavors
        self.tenant_id = tenant_id        
        self.request = request

    def index(self):
        data = []
        for flavor in self.flavors:
            data.append(self.view(flavor, self.tenant_id, request=self.request).show()['flavor'])
        return {"flavors": data}
    
    def index_detail(self):
        data = []
        for flavor in self.flavors:
            data.append(self.view(flavor, self.tenant_id, request=self.request).show()['flavor'])
        return {"flavors": data}
