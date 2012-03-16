# vim: tabstop=4 shiftwidth=4 softtabstop=4

#    Copyright 2012 Hewlett-Packard Development Company, L.P.
#
#    Copyright 2011 OpenStack LLC.
#    All Rights Reserved.
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
import urlparse
import routes
import webob.exc

from reddwarf import rpc
from reddwarf import utils
from reddwarf.common import config
from reddwarf.common import context as rd_context
from reddwarf.common import exception
from reddwarf.common import utils
from reddwarf.common import wsgi
from reddwarf.database import models
from reddwarf.database import views


CONFIG = config.Config
LOG = logging.getLogger(__name__)


class BaseController(wsgi.Controller):
    """Base controller class."""

    exclude_attr = []
    exception_map = {
        webob.exc.HTTPUnprocessableEntity: [
            ],
        webob.exc.HTTPBadRequest: [
            models.InvalidModelError,
            ],
        webob.exc.HTTPNotFound: [
            exception.NotFound,
            models.ModelNotFoundError,
            ],
        webob.exc.HTTPConflict: [
            ],
        }

    def __init__(self):
        pass

    def _extract_required_params(self, params, model_name):
        params = params or {}
        model_params = params.get(model_name, {})
        return utils.stringify_keys(utils.exclude(model_params,
                                                  *self.exclude_attr))


class InstanceController(BaseController):
    """Controller for instance functionality"""

    def index(self, req, tenant_id):
        """Return all instances."""
        LOG.debug("Index() called with %s, %s" % (tenant_id, id))  
        # TODO(hub-cap): turn this into middleware
        context = rd_context.ReddwarfContext(
                          auth_tok=req.headers["X-Auth-Token"],
                          tenant=tenant_id)
        LOG.debug("Context: %s" % context.to_dict())
        servers = models.DBInstance(context=context).list()
        LOG.debug("Index() executed correctly")
        # TODO(cp16net): need to set the return code correctly
        return wsgi.Result(views.DBInstancesView(servers).data(), 200)

    def show(self, req, tenant_id, id):
        """Return a single instance."""
        LOG.debug("Show() called with %s, %s" % (tenant_id, id))
        # TODO(hub-cap): turn this into middleware
        context = rd_context.ReddwarfContext(
                          auth_tok=req.headers["X-Auth-Token"],
                          tenant=tenant_id)
        LOG.debug("Context: %s" % context.to_dict())
        try:
            # TODO(hub-cap): start testing the failure cases here
            server = models.DBInstance(context=context, uuid=id).data()
        except exception.ReddwarfError, e:
            # TODO(hub-cap): come up with a better way than
            #    this to get the message
            LOG.debug("Show() failed with an exception")
            return wsgi.Result(str(e), 404)
        # TODO(cp16net): need to set the return code correctly
        LOG.debug("Show() executed correctly")
        return wsgi.Result(views.DBInstanceView(server).data(), 200)

    def delete(self, req, tenant_id, id):
        """Delete a single instance."""
        LOG.debug("Delete() called with %s, %s" % (tenant_id, id))
        # TODO(hub-cap): turn this into middleware
        context = rd_context.ReddwarfContext(
                          auth_tok=req.headers["X-Auth-Token"],
                          tenant=tenant_id)
        LOG.debug("Delete() context")
        # TODO(cp16net) : need to handle exceptions here if the delete fails
        models.DBInstance.delete(context=context, uuid=id)

        # TODO(cp16net): need to set the return code correctly
        LOG.debug("Returning value")
        return wsgi.Result(None, 204)

    def create(self, req, body, tenant_id):
        
        # find the service id (cant be done yet at startup due to
        # inconsitencies w/ the load app paste
        # TODO(hub-cap): figure out how to get this to work in __init__ time
        # TODO(hub-cap): The problem with this in __init__ is that the paste
        #   config is generated w/ the same config file as the db flags that
        #   are needed for init. These need to be split so the db can be init'd
        #   w/o the paste stuff. Since the paste stuff inits the
        #   database.service module, it is a chicken before the egg problem.
        #   Simple refactor will fix it and we can move this into the __init__
        #   code. Or maybe we shouldnt due to the nature of changing images.
        #   This needs discussion.
        # TODO(hub-cap): turn this into middleware
        LOG.info("Creating a database instance for tenant '%s'" % tenant_id)
        LOG.info("req : '%s'\n\n" % req)
        LOG.info("body : '%s'\n\n" % body)
        context = rd_context.ReddwarfContext(
                          auth_tok=req.headers["X-Auth-Token"],
                          tenant=tenant_id)
        
        database = models.ServiceImage.find_by(service_name="database")
        image_id = database['image_id']
        print context.to_dict(), image_id, body
        
#        flavor = models.ServiceFlavor.find_by(service_name="database")
#        flavor_id = flavor['flavor_id']
#        
#        storage_uri = None
#        if 'snapshotId' in body['instance']:
#            snapshot_id = body['instance']['snapshotId']
#            if snapshot_id and len(snapshot_id) > 0:
#                db_snapshot = dbapi.db_snapshot_get(snapshot_id)
#                storage_uri = db_snapshot.storage_uri
#                LOG.debug("Found Storage URI for snapshot: %s" % storage_uri)
        
        server = models.DBInstance.create().data()
        LOG.debug("Wrote instance: %s" % server)

        # Now wait for the response from the create to do additional work
        #TODO(cp16net): need to set the return code correctly
        return wsgi.Result(views.DBInstanceView(server).data(), 201)

    def restart(self, req, tenant_id, id):
        """Restart an instance."""
        LOG.debug("Called restart() with %s, %s" % (tenant_id, id))
        
        return wsgi.Result(None, 204)
    
    def reset_password(self, req, tenant_id, id):
        """Change the password on an instance."""
        LOG.debug("Called reset_password() with %s, %s" % (tenant_id, id))
        password = utils.generate_password()
        # get instance from DB
        LOG.debug("Triggering smart agent to reset password on Instance %s (%s).", id, instance['hostname'])
        return rpc.call(context, instance['hostname'],
                {"method": "reset_password",
                 "args": {"password": password}},
                timeout, connection_pool)
        
        return wsgi.Result(None, 200)

    def _try_create_server(self):
        pass
    
class SnapshotController(BaseController):
    """Controller for snapshot functionality"""

    def show(self, req, tenant_id, id):
        """Return a list of all snapshots for all instances."""
        LOG.debug("Snapshots.show() called with %s, %s" % (tenant_id, id))
        LOG.debug("Showing all snapshots")
        return wsgi.Result(None, 200)

    def index(self, req, tenant_id):
        """Return a list of all snapshots for a specific instance."""
        LOG.debug("Snapshots.index() called with %s, %s" % (tenant_id, id))

        instance_id = ''
        if req.query_string is not '':
            # returns list of tuples
            name_value_pairs = urlparse.parse_qsl(req.query_string,
                                         keep_blank_values=True,
                                         strict_parsing=False)
            for name_value in name_value_pairs:
                if name_value[0] == 'instanceId':
                    instance_id = name_value[1]
                    break
        
        if instance_id and len(instance_id) > 0:
            LOG.debug("Listing snapshots by instance_id %s", instance_id)
        else:
            LOG.debug("Listing snapshots by tenant_id %s", tenant_id)
        
        return wsgi.Result(None, 200)

    def delete(self, req, tenant_id, id):
        """Delete a single snapshot."""
        LOG.debug("Snapshots.delete() called with %s, %s" % (tenant_id, id))
        LOG.debug("Deleting snapshot")
        return wsgi.Result(None, 204)

    def create(self, req, body, tenant_id):
        """Creates a snapshot."""
        LOG.debug("Snapshots.create() called with %s, %s" % (tenant_id, id))
        LOG.info("Creating a database snapshot for tenant '%s'" % tenant_id)
        LOG.info("req : '%s'\n\n" % req)
        LOG.info("body : '%s'\n\n" % body)
        context = rd_context.ReddwarfContext(
                          auth_tok=req.headers["X-Auth-Token"],
                          tenant=tenant_id)
        
        server = models.Snapshot.create().data()
        LOG.debug("Wrote snapshot: %s" % server)        
        return wsgi.Result(None, 201)
            

class API(wsgi.Router):
    """API"""
    def __init__(self):
        mapper = routes.Mapper()
        super(API, self).__init__(mapper)
        self._instance_router(mapper)
        self._snapshot_router(mapper)

    def _instance_router(self, mapper):
        instance_resource = InstanceController().create_resource()
        path = "/{tenant_id}/instances"
        mapper.resource("instance", path, controller=instance_resource)
        mapper.connect("/{tenant_id}/instances/{id}/restart",
                       controller=instance_resource,
                       action="restart", conditions=dict(method=["POST"]))
        mapper.connect("/{tenant_id}/instances/{id}/resetpassword",
                       controller=instance_resource,
                       action="reset_password", conditions=dict(method=["POST"]))
        
    def _snapshot_router(self, mapper):
        snapshot_resource = SnapshotController().create_resource()
        path = "/{tenant_id}/snapshots"
        mapper.resource("snapshot", path, controller=snapshot_resource)
    

def app_factory(global_conf, **local_conf):
    return API()
