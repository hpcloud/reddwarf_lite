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
import eventlet

from reddwarf import rpc
from reddwarf.common import config
from reddwarf.common import context as rd_context
from reddwarf.common import exception
from reddwarf.common import result_state
from reddwarf.common import utils
from reddwarf.common import wsgi
from reddwarf.database import models
from reddwarf.database import views
from reddwarf.database import guest
from reddwarf.admin import service as admin


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
        servers = models.DBInstance().find_all(tenant_id=tenant_id, deleted=False)
        LOG.debug(servers)
        LOG.debug("Index() executed correctly")
        # TODO(cp16net): need to set the return code correctly
        return wsgi.Result(views.DBInstancesView(servers, req, tenant_id).list(), 200)

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
            server = models.DBInstance().find_by(id=id, tenant_id=tenant_id, deleted=False)
        except exception.ReddwarfError, e:
            # TODO(hub-cap): come up with a better way than
            #    this to get the message
            LOG.debug("Show() failed with an exception")
            return wsgi.Result(str(e), 404)
        # TODO(cp16net): need to set the return code correctly
        LOG.debug("Show() executed correctly")
        return wsgi.Result(views.DBInstanceView(server, req, tenant_id).show(), 200)

    def delete(self, req, tenant_id, id):
        """Delete a single instance."""
        LOG.debug("Delete() called with %s, %s" % (tenant_id, id))
        # TODO(hub-cap): turn this into middleware
        context = rd_context.ReddwarfContext(
                          auth_tok=req.headers["X-Auth-Token"],
                          tenant=tenant_id)
        LOG.debug("Delete() context")                   
        
        try:
            server = models.DBInstance().find_by(id=id, tenant_id=tenant_id, deleted=False)
        except exception.ReddwarfError, e:
            LOG.debug("Fail fetching instance")
            return wsgi.Result(None,404)
        
        remote_id = server.data()["remote_id"]
        try:
            LOG.debug("Deleting remote instance with id %s" % remote_id)
            # TODO(cp16net) : need to handle exceptions here if the delete fails
            models.Instance.delete(context, remote_id)
        except exception.ReddwarfError:
            LOG.debug("Fail Deleting Remote instance")
            return wsgi.Result(None,404)
    
        try:
            server = server.delete()
        except exception.ReddwarfError, e:
            LOG.debug("Fail to delete DB instance")
            return wsgi.Result(None,500)
        
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
        
        flavor = models.ServiceFlavor.find_by(service_name="database")
        flavor_id = flavor['flavor_id']

        LOG.debug("Using ImageID %s" % image_id)
        LOG.debug("Using FlavorID %s" % image_id)        
        storage_uri = None
#        if 'snapshotId' in body['instance']:
#            snapshot_id = body['instance']['snapshotId']
#            if snapshot_id and len(snapshot_id) > 0:
#                try:
#                    # TODO(hub-cap): start testing the failure cases here
#                    server = models.Snapshot(context=context, uuid=id).one()
#                except exception.ReddwarfError, e:
#                    # TODO(hub-cap): come up with a better way than
#                    #    this to get the message
#                    LOG.debug("Show() failed with an exception")
#                    return wsgi.Result(str(e), 404)
#
#                db_snapshot = dbapi.db_snapshot_get(snapshot_id)
#                storage_uri = db_snapshot.storage_uri
#                LOG.debug("Found Storage URI for snapshot: %s" % storage_uri)
        
        server, floating_ip = self._try_create_server(context, body, image_id, flavor_id)
        server_dict = server.data()
        floating_ip_dict = floating_ip.data()
        
        LOG.debug("Wrote instance: %s" % server)
        
        instance = models.DBInstance().create(name=body['instance']['name'],
                                     status='building',
                                     remote_id=server_dict['id'],
                                     remote_uuid=server_dict['uuid'],
                                     remote_hostname=server_dict['name'],
                                     user_id=context.user,
                                     tenant_id=context.tenant,
                                     address=floating_ip_dict['ip'],
                                     port='3306',
                                     flavor=1)

        # Now wait for the response from the create to do additional work
        #TODO(cp16net): need to set the return code correctly

        return wsgi.Result(views.DBInstanceView(instance.data(), req, tenant_id).create(), 201)

    def restart(self, req, tenant_id, id):
        """Restart an instance."""
        LOG.debug("Called restart() with %s, %s" % (tenant_id, id))
        
        return wsgi.Result(None, 204)
    
    def reset_password(self, req, tenant_id, id):
        """Resets DB password on remote instance"""
        LOG.info("Resets DB password on Instance %s", id)
#        password = utils.generate_password()
#        context = req.environ['nova.context']
#        result = self.guest_api.reset_password(context, id, password)
#        if result == result_state.ResultState.SUCCESS:
#            return {'password': password}
#        else:
#            LOG.debug("Smart Agent failed to reset password (RPC response: '%s').",
#                result_state.ResultState.name(result))
#            return exc.HTTPInternalServerError("Smart Agent failed to reset password.")

        
        return wsgi.Result(None, 200)

    def _try_create_server(self, context, body, image_id, flavor_id, snapshot_uri=None):
        """Create remote Server """
        try:
            # TODO(vipulsabhaya): Create a ServiceSecgroup model
            sec_group = ['mysql']

            conf_file = '[messaging]\n'\
                        'rabbit_host: ' + 'localhost' + '\n'\
                        '\n'\
                        '[database]\n'\
                        'initial_password: ' + utils.generate_password(length=8)

            LOG.debug('%s',conf_file)

            files = { '/home/nova/agent.config': conf_file }
            keypair = 'dbas-dev'
            
            userdata = open('../development/bootstrap/dbaas-image.sh')

            floating_ip = models.FloatingIP.create(context)
            if floating_ip is None:
                print "No Floating IP assigned!"
            server = models.Instance.create(context, body, image_id, flavor_id, 
                                            security_groups=sec_group, key_name=keypair,
                                            userdata=userdata, files=files)
            
            if not server:
                raise exception.ReddwarfError("Remote server not created")
            
            server_dict = server.data()
            flip_dict = floating_ip.data()
            print server_dict
            self._try_assign_ip(context, server_dict, flip_dict)
            
            return server, floating_ip
        except (Exception) as e:
            LOG.error(e)
            raise exception.ReddwarfError(e)

    def _try_assign_ip(self, context, server, floating_ip):
        print "attempt to assign ip"
        success = False
        for i in range(90):
            try:          
                #print "attempt to assign ip 2 " + floating_ip['ip'] + " x:" + str(server['id'])
                models.FloatingIP.assign(context, floating_ip, server['id'])
                success = True
                break
            except Exception:
                success = False
                eventlet.sleep(1)
                
        if not success:
            raise exception.ReddwarfError("Unable to assign IP to database instance")                


class SnapshotController(BaseController):
    """Controller for snapshot functionality"""

    def show(self, req, tenant_id, id):
        """Return information about a specific snapshot."""
        LOG.debug("Snapshots.show() called with %s, %s" % (tenant_id, id))
        LOG.debug("Showing all snapshots")
        
#        context = rd_context.ReddwarfContext(
#                          auth_tok=req.headers["X-Auth-Token"],
#                          tenant=tenant_id)
#        LOG.debug("Context: %s" % context.to_dict())
        
        server = models.Snapshot().find_by(id=id)
        LOG.debug("Servers: %s" % server)       
        return wsgi.Result(views.SnapshotView(server).show(), 200)

    def index(self, req, tenant_id):
        """Return a list of all snapshots for a specific instance or tenant."""
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

        context = rd_context.ReddwarfContext(
                          auth_tok=req.headers["X-Auth-Token"],
                          tenant=tenant_id)
        LOG.debug("Context: %s" % context.to_dict())
        
        if instance_id and len(instance_id) > 0:
            LOG.debug("Listing snapshots by instance_id %s", instance_id)
            servers = models.Snapshot().list_by_instance(instance_id)
            LOG.debug("Servers: %s" % servers)
            return wsgi.Result(views.SnapshotsView(servers).list(), 200)
        else:
            LOG.debug("Listing snapshots by tenant_id %s", tenant_id)            
            servers = models.Snapshot().list_by_tenant(tenant_id)
            LOG.debug("Servers: %s" % servers)
            return wsgi.Result(views.SnapshotsView(servers).list(), 200)

    def delete(self, req, tenant_id, id):
        """Delete a single snapshot."""
        LOG.debug("Snapshots.delete() called with %s, %s" % (tenant_id, id))
        LOG.debug("Deleting snapshot")
        
        context = rd_context.ReddwarfContext(
                          auth_tok=req.headers["X-Auth-Token"],
                          tenant=tenant_id)
        LOG.debug("Delete() context") 
        
        try:
            snapshot = models.Snapshot().find_by(id=id)
        except exception.ReddwarfError, e:
            LOG.debug("Fail fetching instance")
            return wsgi.Result(None,404)
    
        try:
            server = models.Snapshot().find_by(id=id).delete()
        except exception.ReddwarfError, e:
            LOG.debug("Fail to delete DB instance")
            return wsgi.Result(None,500)
        
        # TODO(cp16net): need to set the return code correctly
        LOG.debug("Returning value")              
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
        LOG.debug("Context: %s" % context.to_dict())
        snapshot = models.Snapshot().create(name=body['snapshot']['name'],
                                     instance_id=body['snapshot']['instanceId'],
                                     state='building',
                                     user_id=context.user,
                                     tenant_id=context.tenant)
        LOG.debug("Wrote snapshot: %s" % snapshot)        
        return wsgi.Result(None, 201)
                 

class API(wsgi.Router):
    """API"""
    def __init__(self):
        mapper = routes.Mapper()
        super(API, self).__init__(mapper)
        self._instance_router(mapper)
        self._snapshot_router(mapper)
        self._admin_router(mapper)

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

    def _admin_router(self, mapper):
        admin_resource = admin.AdminController().create_resource()
        mapper.connect("/{tenant_id}/mgmt/{id}/agent",
                       controller=admin_resource,
                       action="agent", conditions=dict(method=["POST"]))
        mapper.connect("/{tenant_id}/mgmt/{id}/messageserver",
                       controller=admin_resource,
                       action="message_server", conditions=dict(method=["POST"]))
        mapper.connect("/{tenant_id}/mgmt/{id}/database",
                       controller=admin_resource,
                       action="database", conditions=dict(method=["POST"]))
        

def app_factory(global_conf, **local_conf):
    return API()
