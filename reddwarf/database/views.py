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

logging.basicConfig()

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)

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
    
    def __init__(self, instance):
        self.instance = instance
        
    def _build_create(self):
        LOG.debug(self.instance)

        return {"instance": {
                    "status": self.instance['status'], 
#                    "links": self._build_links(self.instance['links']),    
                    "name": self.instance['name'],
                    "id": self.instance['id'],                        
                    "remote_hostname": self.instance['remote_hostname'],
                    "created_at": self.instance['created_at'],            
                    "credential": self.instance['credential'],
                } 
        } 
 
    def _build_list(self):
        LOG.debug("INSTANCE: %s" % self.instance)
            
        # TODO: add links to each view, fix 'instances' on list/aggregation
        return {"status": self.instance['status'],                    
                "id": self.instance['id'],                
#                "links": self._build_links(self.instance['links']),       
                "name": self.instance['name'],
                "created_at": self.instance['created_at'],                
        }
        
    def _build_show(self):
        LOG.debug(self.instance)

        return {"instance": {
                    "status": self.instance['status'],    
#                    "links": self._build_links(self.instance['links']),                
                    "name": self.instance['name'],
                    "id": self.instance['id'],            
                    "remote_hostname": self.instance['remote_hostname'],
                    "created_at": self.instance['created_at'],  
                    "port": self.instance['port'],          
                    "updated_at": self.instance['updated_at'],
                } 
        }         
        
    @staticmethod
    def _build_links(links):
        """Build the links for the instance"""
        LOG.debug(links)
        for link in links:
            LOG.debug(link)
            try:
                link['href'] = link['href'].replace('servers', 'instances')
            except Exception, err:
                continue
        return links               

    def list(self):
        return self._build_list()
    
    def show(self):
        return self._build_show()
    
    def create(self):
        return self._build_create()


class SnapshotView(object):
    
    def __init__(self, snapshot):
        self.snapshot = snapshot
        
    def _build_create(self):
        LOG.debug(self.snapshot)

        return {"snapshot": {
            "id": self.snapshot['id'],
            "status": self.snapshot['status'],
            "created_at": self.snapshot['created_at'],
            "instanceId": self.snapshot['instance_id'],
            # Links  
            },
        } 
 
    def _build_list(self):
        LOG.debug(self.snapshot)
            
        return {"id": self.snapshot['id'],
                "created_at": self.snapshot['created_at'],
                "instanceId": self.snapshot['instance_id'],
                # Links  
        }
        
    def _build_show(self):
        LOG.debug(self.snapshot)

        return {"snapshot": {
            "id": self.snapshot['id'],
            "status": self.snapshot['status'],
            "created_at": self.snapshot['created_at'],
            "instanceId": self.snapshot['instance_id'],
            # Links  
            },
        }         
        
    @staticmethod
    def _build_links(links):
        """Build the links for the snapshot"""
        LOG.debug(links)
        for link in links:
            LOG.debug(link)
            try:
                link['href'] = link['href'].replace('servers', 'snapshots')
            except Exception, err:
                continue
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

    def __init__(self, instances):
        self.instances = instances
        LOG.debug(dir(self.instances))

    def list(self):
        data = []
        LOG.debug("Instances: %s" % self.instances)
        # These are model instances
        for instance in self.instances:
            LOG.debug(instance)
            data.append(DBInstanceView(instance).list())
        LOG.debug("Returning from DBInstancesView.data()")
        return {"instances": data}

class SnapshotsView(object):
    
    def __init__(self, snapshots):
        self.snapshots = snapshots
        LOG.debug(self.snapshots)

    def list(self):
        data = []
        LOG.debug("Snapshot: %s" % self.snapshots)
        # These are model snapshots
        for snapshot in self.snapshots:
            LOG.debug("Snapshot %s" % snapshot)
            data.append(SnapshotView(snapshot).list())
        LOG.debug("Returning from SnapshotsView.data()")
        return {"snapshots" : data}