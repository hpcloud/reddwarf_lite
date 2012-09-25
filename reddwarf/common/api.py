#    Copyright 2012 OpenStack LLC
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

import routes
import logging

from reddwarf.versions import VersionsController
from reddwarf.common import wsgi
from reddwarf.database.service import InstanceController
from reddwarf.database.service import SnapshotController
from reddwarf.flavor.service import FlavorController
from reddwarf.securitygroup.service import SecurityGroupController
from reddwarf.securitygroup.service import SecurityGroupRuleController

LOG = logging.getLogger(__name__)


class API(wsgi.Router):
    """API"""
    def __init__(self):
        mapper = routes.Mapper()
        super(API, self).__init__(mapper)
        self._versions_router(mapper)
        self._instance_router(mapper)
        self._snapshot_router(mapper)
        self._flavor_router(mapper)
        self._security_group_router(mapper)
        self._security_group_rules_router(mapper)
        
    def _has_body(self, environ, result):
        LOG.debug("has body ENVIRON: %s" % environ)
        LOG.debug("RESULT: %s" % result)
        if environ.get("CONTENT_LENGTH") and int(environ.get("CONTENT_LENGTH")) > 0:
            return True
        else:
            return False
        
    def _has_no_body(self, environ, result):
        LOG.debug("has no body ENVIRON: %s" % environ)
        LOG.debug("RESULT: %s" % result)
        LOG.debug(environ.get("CONTENT_LENGTH"))
        
        if not environ.get("CONTENT_LENGTH"):
            return True  
        elif int(environ.get("CONTENT_LENGTH")) > 0:
            return False
        else:            
            return True
        
    def _versions_router(self, mapper):
        versions_resource = VersionsController().create_resource()
        mapper.connect("/",
                       controller=versions_resource,
                       action="show", conditions=dict(method=["GET"],
                                                      function=self._has_no_body))

    def _instance_router(self, mapper):
        instance_resource = InstanceController().create_resource()
        path = "/{tenant_id}/instances"
      
        mapper.connect(path,
                       controller=instance_resource,
                       action="create", conditions=dict(method=["POST"],
                                                        function=self._has_body))
        mapper.connect(path,
                       controller=instance_resource,
                       action="index", conditions=dict(method=["GET"],
                                                       function=self._has_no_body))                  
        mapper.connect(path + "/{id}",
                       controller=instance_resource,
                       action="show", conditions=dict(method=["GET"],
                                                      function=self._has_no_body))
        mapper.connect(path + "/{id}",
                       controller=instance_resource,
                       action="delete", conditions=dict(method=["DELETE"],
                                                        function=self._has_no_body))              
        mapper.connect(path +"/{id}/restart",
                       controller=instance_resource,
                       action="restart", conditions=dict(method=["POST"],
                                                         function=self._has_no_body))
        mapper.connect(path + "/{id}/resetpassword",
                       controller=instance_resource,
                       action="reset_password", conditions=dict(method=["POST"],
                                                                function=self._has_no_body))
        mapper.connect(path +"/{id}/action",
                       controller=instance_resource,
                       action="action", conditions=dict(method=["POST"],
                                                         function=self._has_body))
        
    def _snapshot_router(self, mapper):
        snapshot_resource = SnapshotController().create_resource()
        path = "/{tenant_id}/snapshots"

        mapper.connect(path,
                       controller=snapshot_resource,
                       action="create", conditions=dict(method=["POST"],
                                                        function=self._has_body))        
        mapper.connect(path,
                       controller=snapshot_resource,
                       action="index", conditions=dict(method=["GET"],
                                                       function=self._has_no_body))
        mapper.connect(path + "/{id}",
                       controller=snapshot_resource,
                       action="show", conditions=dict(method=["GET"],
                                                      function=self._has_no_body))
        mapper.connect(path + "/{id}",
                       controller=snapshot_resource,
                       action="delete", conditions=dict(method=["DELETE"],
                                                        function=self._has_no_body))  

    def _flavor_router(self, mapper):
        flavor_resource = FlavorController().create_resource()
        path = "/{tenant_id}/flavors"
        mapper.connect(path, 
                       controller=flavor_resource,
                       action="index", conditions=dict(method=["GET"],
                                                       function=self._has_no_body))
        mapper.connect(path + "/detail", 
                       controller=flavor_resource,
                       action="index_detail", conditions=dict(method=["GET"],
                                                              function=self._has_no_body))
        
        mapper.connect(path + "/{id}", 
                       controller=flavor_resource,
                       action="show", conditions=dict(method=["GET"],
                                                      function=self._has_no_body))        

    def _security_group_router(self, mapper):
        secgroup_resource = SecurityGroupController().create_resource()
        path = "/{tenant_id}/security-groups"
        mapper.resource("security-group", path, controller=secgroup_resource)
        
    def _security_group_rules_router(self, mapper):
        secgroup_rule_resource = SecurityGroupRuleController().create_resource()
        path = "/{tenant_id}/security-group-rules"
        mapper.connect(path,
                       controller=secgroup_rule_resource,
                       action="create", conditions=dict(method=["POST"],
                                                        function=self._has_body))
        mapper.connect(path + "/{id}",
                       controller=secgroup_rule_resource,
                       action="delete", conditions=dict(method=["DELETE"],
                                                        function=self._has_no_body))



def app_factory(global_conf, **local_conf):
    return API()