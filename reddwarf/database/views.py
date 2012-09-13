# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2011 OpenStack LLC.
# All Rights Reserved.
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

import logging
import os

LOG = logging.getLogger(__name__)

def _base_url(req):
    return req.application_url


class InstanceView(object):

    def __init__(self, instance):
        self.instance = instance

    def data(self):
        return {"instance": {
                    "id": self.instance['id'],
                    "name": self.instance['name'],
                    "status": self.instance['status'],
                    "created": self.instance['created'],
                    "updated": self.instance['updated'],
                    "flavor": self.instance['flavor'],
#                    "links": self._build_links(self.instance['links']),
                    "addresses": self.instance['addresses'],
            },
        }

    @staticmethod
    def _build_links(links):
        """Build the links for the instance"""
        for link in links:
            link['href'] = link['href'].replace('servers', 'instances')
        return links

class DBInstanceView(object):
    
    def __init__(self, instance, guest_status, security_groups, req, tenant_id):
        self.instance = instance
        self.guest_status = guest_status
        self.security_groups = security_groups
        self.request = req
        self.tenant_id = tenant_id
        
    def _build_create(self, initial_user, initial_password):
        credential = { "username" : initial_user,
                       "password" : initial_password }
        return {"instance": {
                    "status": self.guest_status['state'], 
                    "links": self._build_links(),    
                    "name": self.instance['name'],
                    "id": self.instance['id'],                        
                    "hostname": "" if self.instance['address'] is None else self.instance['address'],
                    "security_groups": self._build_secgroups(),
                    "created": self.instance['created_at'],            
                    "credential": credential
                } 
        } 
 
    def _build_list(self):
        # TODO: add links to each view, fix 'instances' on list/aggregation
        return {"status": self.guest_status['state'],                    
                "id": self.instance['id'],                
                "links": self._build_links(),       
                "name": self.instance['name'],
                "created": self.instance['created_at'],                
        }
        
    def _build_show(self):
        return {"instance": {
                    "status": self.guest_status['state'],    
                    "links": self._build_links(),                
                    "name": self.instance['name'],
                    "id": self.instance['id'],            
                    "hostname": "" if self.instance['address'] is None else self.instance['address'],
                    "security_groups": self._build_secgroups(),
                    "created": self.instance['created_at'],  
                    "port": self.instance['port'],          
                    "updated": self.instance['updated_at'],
                } 
        }         
        
    def _build_links(self):
        """Build the links for the instance"""
        base_url = _base_url(self.request)
        href = os.path.join(base_url, self.tenant_id,
                            "instances", str(self.instance['id']))
        links = [
            {
                'rel': 'self',
                'href': href
            }
        ]
        return links       
    
    def _build_secgroups(self):
        groups = []
        
        if self.security_groups is None:
            return groups
        
        for group in self.security_groups:
            groups.append({
                            'id': group['id'],
                            'links': self._build_secgroup_links(group['id'])
                        })
        return groups        
        
    def _build_secgroup_links(self, id):
        """Build the links for the instance"""
        base_url = _base_url(self.request)
        href = os.path.join(base_url, self.tenant_id,
                            "security-groups", str(id))
        links = [
            {
                'rel': 'self',
                'href': href
            }
        ]
        return links   

    def list(self):
        return self._build_list()
    
    def show(self):
        return self._build_show()
    
    def create(self, initial_user, initial_password):
        return self._build_create(initial_user, initial_password)


class SnapshotView(object):
    
    def __init__(self, snapshot, req, tenant_id):
        self.snapshot = snapshot
        self.request = req
        self.tenant_id = tenant_id
        
    def _build_create(self):

        return {"snapshot": {
            "id": self.snapshot['id'],
            "status": self.snapshot['state'],
            "created": self.snapshot['created_at'],
            "instanceId": self.snapshot['instance_id'],
            "links": self._build_links()       
            }
        } 
 
    def _build_list(self):
            
        return {"id": self.snapshot['id'],
                "created": self.snapshot['created_at'],
                "instanceId": self.snapshot['instance_id'],
                "links": self._build_links() 
        }
        
    def _build_show(self):

        return {"snapshot": {
            "id": self.snapshot['id'],
            "status": self.snapshot['state'],
            "created": self.snapshot['created_at'],
            "instanceId": self.snapshot['instance_id'],
            "links": self._build_links()
            },
        }         
        
    def _build_links(self):
        """Build the links for the instance"""
        base_url = _base_url(self.request)
        href = os.path.join(base_url, self.tenant_id,
                            "snapshots", str(self.snapshot['id']))
        links = [
            {
                'rel': 'self',
                'href': href
            }
        ]
        return links 
    
    def list(self):
        return self._build_list()
    
    def show(self):
        return self._build_show()
    
    def create(self):
        return self._build_create()

class InstancesView(object):

    def __init__(self, instances):
        self.instances = instances

    def data(self):
        data = []
        # These are model instances
        for instance in self.instances:
            data.append(InstanceView(instance).data())
        LOG.debug("Returning from InstancesView.data()")
        return data
    
class DBInstancesView(object):

    def __init__(self, instances, guest_statuses, req, tenant_id):
        self.instances = instances
        self.guest_statuses = guest_statuses
        self.request = req
        self.tenant_id = tenant_id
        LOG.debug(dir(self.instances))

    def list(self):
        data = []
        LOG.debug("Instances View Builder: %s" % self.instances)
        # These are model instances
        for instance in self.instances:
            LOG.debug("Instance to include into List: %s" % instance)
            guest_status = self.guest_statuses[instance['id']]
            LOG.debug("GuestStatus for instance: %s" % guest_status)
            data.append(DBInstanceView(instance, guest_status, None, self.request, self.tenant_id).list())
        LOG.debug("Returning from DBInstancesView.data()")
        return {"instances": data}

class SnapshotsView(object):
    
    def __init__(self, snapshots, req, tenant_id):
        self.snapshots = snapshots
        self.request = req
        self.tenant_id = tenant_id
        LOG.debug(self.snapshots)

    def list(self):
        data = []
        LOG.debug("Snapshot: %s" % self.snapshots)
        # These are model snapshots
        for snapshot in self.snapshots:
            LOG.debug("Snapshot %s" % snapshot)
            data.append(SnapshotView(snapshot, self.request, self.tenant_id).list())
        LOG.debug("Returning from SnapshotsView.data()")
        return {"snapshots" : data}