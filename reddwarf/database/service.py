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

from reddwarf import db
from reddwarf.common import config
from reddwarf.common import context as rd_context
from reddwarf.common import errors
from reddwarf.common import exception
from reddwarf.common import result_state
from reddwarf.common import utils
from reddwarf.common import wsgi
from reddwarf.database import models
from reddwarf.database import views
from reddwarf.database import guest_api
from reddwarf.database import worker_api
from reddwarf.admin import service as admin
from swiftapi import swift


CONFIG = config.Config
GUEST_API = guest_api.API
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
        self.guest_api = guest_api.API()

    def _extract_required_params(self, params, model_name):
        params = params or {}
        model_params = params.get(model_name, {})
        return utils.stringify_keys(utils.exclude(model_params,
                                                  *self.exclude_attr))


class InstanceController(BaseController):
    """Controller for instance functionality"""
    
    def index(self, req, tenant_id):
        """Return all instances tied to a particular tenant_id."""
        LOG.debug("Index() called with %s, %s" % (tenant_id, id))  
        # TODO(hub-cap): turn this into middleware
        context = req.context
        LOG.debug("Context: %s" % context.to_dict())
        servers = models.DBInstance().find_all(tenant_id=tenant_id, deleted=False)
        LOG.debug(servers)
        
        id_list = [server['id'] for server in servers]
        guest_states = self.get_guest_state_mapping(id_list)
        
        LOG.debug("Index() executed correctly")
        # TODO(cp16net): need to set the return code correctly
        return wsgi.Result(views.DBInstancesView(servers, guest_states, req, tenant_id).list(), 200)

    def show(self, req, tenant_id, id):
        """Return a single instance."""
        LOG.debug("Show() called with %s, %s" % (tenant_id, id))
        # TODO(hub-cap): turn this into middleware
        context = rd_context.ReddwarfContext(
                          auth_tok=req.headers["X-Auth-Token"],
                          tenant=tenant_id)
        LOG.debug("Context: %s" % context.to_dict())
        try:
            server = models.DBInstance().find_by(id=id, tenant_id=tenant_id, deleted=False)
        except exception.ReddwarfError, e:
            LOG.debug("Show() failed with an exception")
            return wsgi.Result(errors.wrap(errors.Instance.NOT_FOUND), 404)

        try:
            guest_status = models.GuestStatus().find_by(instance_id=server['id'], deleted=False)
        except exception.ReddwarfError, e:
            LOG.debug("Show() failed with an exception")
            return wsgi.Result(errors.wrap(errors.Instance.NOT_FOUND), 404)

        # TODO(cp16net): need to set the return code correctly
        LOG.debug("Show() executed correctly")
        return wsgi.Result(views.DBInstanceView(server, guest_status, req, tenant_id).show(), 200)

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
            return wsgi.Result(errors.wrap(errors.Instance.NOT_FOUND), 404)
        
        remote_id = server["remote_id"]
        credential = models.Credential().find_by(id=server['credential'])
        
        # Try to delete the Nova instance
        try:
            LOG.debug("Deleting remote instance with id %s" % remote_id)
            # TODO(cp16net) : need to handle exceptions here if the delete fails
            models.Instance.delete(credential, remote_id)
        except exception.ReddwarfError:
            LOG.debug("Fail Deleting Remote instance")
            return wsgi.Result(errors.wrap(errors.Instance.NOVA_DELETE), 404)

        # Try to delete the Reddwarf lite instance
        try:
            server = server.delete()
        except exception.ReddwarfError, e:
            LOG.debug("Fail to delete DB instance")
            return wsgi.Result(errors.wrap(errors.Instance.REDDWARF_DELETE), 500)
        
        # Finally, try to delete the associated GuestStatus record
        try:
            guest_status = models.GuestStatus().find_by(instance_id=server['id'])
            guest_status.delete()
        except exception.ReddwarfError, e:
            LOG.debug("Failed to delete GuestStatus record")
            return wsgi.Result(errors.wrap(errors.Instance.GUEST_DELETE), 500)
        
        
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
        LOG.debug("Using FlavorID %s" % flavor_id)        
        
        try:
            snapshot = self._extract_snapshot(body, tenant_id)
        except exception.ReddwarfError, e:
            LOG.debug("Error creating Reddwarf instance: %s" % e)
            return wsgi.Result(errors.wrap(errors.Snapshot.NOT_FOUND), 500)
        except Exception, e:
            return wsgi.Result(errors.wrap(errors.Instance.MALFORMED_BODY), 500)
        
        # Get the credential to use for proxy compute resource
        credential = models.Credential.find_by(type='compute')
        password = utils.generate_password(length=8)
        
        try:
            server, floating_ip = self._try_create_server(context, body, credential, image_id, flavor_id, snapshot, password)
        except exception.ReddwarfError, e:
            LOG.debug("E: %s" % e)
            if "RAMLimitExceeded" in e:
                LOG.debug("Quota exceeded on create instance: %s" % e)
                return wsgi.Result(errors.wrap(errors.Instance.QUOTA_EXCEEDED), 500)
            else:
                LOG.debug("Error creating Nova instance: %s" % e)
                return wsgi.Result(errors.wrap(errors.Instance.NOVA_CREATE), 500)
            
        LOG.debug("Wrote remote server: %s" % server)
        try:
            instance = models.DBInstance().create(name=body['instance']['name'],
                                     status='building',
                                     remote_id=server['id'],
                                     remote_uuid=server['uuid'],
                                     remote_hostname=server['name'],
                                     user_id=context.user,
                                     tenant_id=context.tenant,
                                     credential=credential['id'],
                                     address=floating_ip['ip'],
                                     port='3306',
                                     flavor=1)
        except exception.ReddwarfError, e:
            LOG.debug("Error creating Reddwarf instance: %s" % e)
            return wsgi.Result(errors.wrap(errors.Instance.REDDWARF_CREATE), 500)
            
        LOG.debug("Wrote DB Instance: %s" % instance)
        
        # Add a GuestStatus record pointing to the new instance for Maxwell
        try:
            guest_status = models.GuestStatus().create(instance_id=instance['id'], state='building')
        except exception.ReddwarfError, e:
            LOG.debug("Error deleting GuestStatus instance %s" % instance.data()['id'])
            return wsgi.Result(errors.wrap(errors.Instance.GUEST_CREATE), 500)

        # Invoke worker to ensure instance gets created
        worker_api.API().ensure_create_instance(None, instance)
        
        return wsgi.Result(views.DBInstanceView(instance, guest_status, req, tenant_id).create('dbas', password), 201)


    def restart(self, req, tenant_id, id):
        """Restart an instance."""
        LOG.debug("Called restart() with %s, %s" % (tenant_id, id))
        context = rd_context.ReddwarfContext(
                          auth_tok=req.headers["X-Auth-Token"],
                          tenant=tenant_id)        

        try:
            instance = models.DBInstance().find_by(id=id)
        except exception.ReddwarfError, e:
            LOG.debug("Could not find db instance: %s" % id)
            return wsgi.Result(errors.wrap(errors.Instance.NOT_FOUND), 404)

        # Make sure the guest instance is in running state
        try:
            guest = models.GuestStatus().find_by(instance_id=id)
        except exception.ReddwarfError, e:
            LOG.debug("Could not find DB instance in guest_status table: %s" % id)
            return wsgi.Result(errors.wrap(errors.Instance.NOT_FOUND), 404)

        guest_data = guest.data()
        if not guest_data['state']:
            LOG.debug("The instance %s is not in running state." % id)
            return wsgi.Result(errors.wrap(errors.Instance.INSTANCE_NOT_RUNNING), 403)

        if guest_data['state'] != result_state.ResultState.name(result_state.ResultState.RUNNING):
            LOG.debug("The instance %s is locked due to operation in progress." % id)
            return wsgi.Result(errors.wrap(errors.Instance.INSTANCE_LOCKED), 423)

        instance_data = instance.data()
        credential = models.Credential().find_by(id=instance_data['credential'])
        try:
            models.Instance.restart(credential, instance_data['remote_uuid'])
        except exception.ReddwarfError, e:
            LOG.debug("Could not restart instance: %s" % instance_data['remote_uuid'])
            return wsgi.Result(errors.wrap(errors.Instance.RESTART), 500)

        guest.update(state=result_state.ResultState.name(result_state.ResultState.RESTARTING))
        return wsgi.Result(None, 204)


    def reset_password(self, req, tenant_id, id):
        """Resets DB password on remote instance"""
        LOG.info("Resets DB password on Instance %s", id)
        LOG.debug("Req.environ: %s" % req.environ)

        # Return if instance is not found
        try:
            instance = models.GuestStatus().find_by(instance_id=id)
        except exception.ReddwarfError, e:
            LOG.debug("Could not find DB instance in guest_status table: %s" % id)
            return wsgi.Result(errors.wrap(errors.Instance.NOT_FOUND), 404)

        # Return when instance is not in running state
        data = instance.data()
        if not data['state']:
            LOG.debug("The instance %s is not in running state." % id)
            return wsgi.Result(errors.wrap(errors.Instance.INSTANCE_NOT_RUNNING), 403)

        if data['state'] != result_state.ResultState.name(result_state.ResultState.RUNNING):
            LOG.debug("The instance %s is locked for operation in progress." % id)
            return wsgi.Result(errors.wrap(errors.Instance.INSTANCE_LOCKED), 423)

        # Generate password
        password = utils.generate_password()
        context = rd_context.ReddwarfContext(
                          auth_tok=req.headers["X-Auth-Token"],
                          tenant=tenant_id)

        # Dispatch the job to Smart Agent
        try:
            result = self.guest_api.reset_password(context, id, password)
        except exception.NotFound as nf:
            LOG.debug("Could not find instance: %s" % id)
            return wsgi.Result(errors.wrap(errors.Instance.NOT_FOUND), 404)
        except exception.ReddwarfError as e:
            LOG.exception("Smart Agent failed to reset password.")
            return wsgi.Result(errors.wrap(errors.Instance.RESET_PASSWORD), 500)
        
        # Return response
        if result == result_state.ResultState.SUCCESS:
            return wsgi.Result({'password': password}, 200)
        else:
            LOG.debug("Smart Agent failed to reset password (RPC response: '%s')." % result)
            return wsgi.Result(errors.wrap(errors.Instance.RESET_PASSWORD), 500)


    def _try_create_server(self, context, body, credential, image_id, flavor_id, snapshot=None, password=None):
        """Create remote Server """
        try:
            # TODO (vipulsabhaya) move this into the db we should
            # have a service_secgroup table for mapping
            sec_group = ['mysql']

            conf_file = self._create_boot_config_file(snapshot, password)
            LOG.debug('%s',conf_file)

            #TODO (vipulsabhaya) move this to config or db
            keypair = 'dbas-dev'
            
            userdata = None
            #userdata = open('../development/bootstrap/dbaas-image.sh')

            floating_ip = models.FloatingIP.create(credential).data()

            server = models.Instance.create(credential, body, image_id, flavor_id, 
                                            security_groups=sec_group, key_name=keypair,
                                            userdata=userdata, files=conf_file).data()
            
            if not server:
                raise exception.ReddwarfError(errors.Instance.NOVA_CREATE)
            
            self._try_assign_ip(credential, server, floating_ip)
            
            return (server, floating_ip)
        except (Exception) as e:
            LOG.error(e)
            raise exception.ReddwarfError(e)

    def _try_assign_ip(self, credential, server, floating_ip):
        LOG.debug("Attempt to assign IP %s to instance %s" % (floating_ip['ip'], server['id']));
        success = False
        for i in range(90):
            try:          
                models.FloatingIP.assign(credential, floating_ip, server['id'])
                success = True
                break
            except Exception:
                success = False
                eventlet.sleep(1)
                
        if not success:
            raise exception.ReddwarfError(errors.Instance.IP_ASSIGN)                

    def _extract_snapshot(self, body, tenant_id):

        if 'instance' not in body:
            LOG.debug("The body passed to create was malformed")
            raise Exception

        if 'snapshotId' in body['instance']:
            snapshot_id = body['instance']['snapshotId']
            if snapshot_id and len(snapshot_id) > 0:
                try:
                    snapshot = models.Snapshot().find_by(id=snapshot_id, tenant_id=tenant_id, deleted=False)
                    return snapshot
                except exception.ReddwarfError, e:
                    LOG.debug("No Snapshot Record with id %s" % snapshot_id)
                    raise e

    def _create_boot_config_file(self, snapshot, password):
        """Creates a config file that gets placed in the instance
        for the Agent to configure itself"""
        
        RABBIT_HOST = CONFIG.get('rabbit_host', 'localhost')
        RABBIT_PORT = CONFIG.get('rabbit_port', '5672')
        RABBIT_SSL = CONFIG.get('rabbit_use_ssl', 'False')
        conf_file = '[messaging]\n'\
                    'rabbit_host: ' + RABBIT_HOST + '\n'\
                    'rabbit_port: ' + RABBIT_PORT + '\n'\
                    'rabbit_use_ssl: ' + RABBIT_SSL + '\n'\
                    '\n'\
                    '[database]\n'\
                    'initial_password: ' + password
        
        storage_uri = None
        if snapshot:
            storage_uri = snapshot['storage_uri']
            
        if storage_uri and len(storage_uri) > 0:
            #Fetch the swift credentials
            credential = models.Credential().find_by(id=snapshot['credential'])
            conf_file = conf_file + '\n'\
                           '[snapshot]\n'\
                           'snapshot_uri: ' + storage_uri + '\n'\
                           'swift_auth_url: ' + CONFIG.get('reddwarf_proxy_swift_auth_url', 'http://0.0.0.0:5000/v2.0')+ '\n'\
                           'swift_auth_user: ' + credential['tenant_id'] + ":" + credential['user_name'] + '\n'\
                           'swift_auth_key: ' + credential['password'] + '\n'

        return { '/home/nova/agent.config': conf_file }

    def get_guest_state_mapping(self, id_list):
        """Returns a dictionary of guest statuses keyed by guest ids."""
        results = db.db_api.find_guest_statuses_for_instances(id_list)
        return dict([(r.instance_id, r) for r in results])

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
        try:
            snapshot = models.Snapshot().find_by(id=id, deleted=False)
        except exception.ReddwarfError, e:            
            LOG.debug("Show() failed with an exception")
            return wsgi.Result(errors.wrap(errors.Snapshot.NOT_FOUND), 404)    
        
        LOG.debug("Show Snapshot: %s" % snapshot)       
        return wsgi.Result(views.SnapshotView(snapshot, req, tenant_id).show(), 200)

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
            snapshots = models.Snapshot().list_by_instance(instance_id)
            LOG.debug("snapshots: %s" % snapshots)
            return wsgi.Result(views.SnapshotsView(snapshots, req, tenant_id).list(), 200)
        else:
            LOG.debug("Listing snapshots by tenant_id %s", tenant_id)            
            snapshots = models.Snapshot().list_by_tenant(tenant_id)
            LOG.debug("snapshots: %s" % snapshots)
            return wsgi.Result(views.SnapshotsView(snapshots, req, tenant_id).list(), 200)

    def delete(self, req, tenant_id, id):
        """Delete a single snapshot."""
        LOG.debug("Snapshots.delete() called with %s, %s" % (tenant_id, id))
        LOG.debug("Deleting snapshot")
        
        context = rd_context.ReddwarfContext(
                          auth_tok=req.headers["X-Auth-Token"],
                          tenant=tenant_id)
        LOG.debug("Delete() context") 
        
        snapshot = None
        try:
            snapshot = models.Snapshot().find_by(id=id)
        except exception.ReddwarfError, e:
            LOG.debug("Fail fetching instance")
            return wsgi.Result(errors.wrap(errors.Snapshot.NOT_FOUND), 404)
        
        data = snapshot.data()
        uri = data['storage_uri']
        
        if uri and len(uri) > 0:
            container, file = uri.split('/',2)

            LOG.debug("Deleting from Container: %s - File: %s", container, file)

            credential = models.Credential.find_by(type='object-store')
            LOG.debug("Got credential: %s" % credential)

            ST_AUTH = CONFIG.get('reddwarf_proxy_swift_auth_url', 'http://0.0.0.0:5000/v2.0')
         
            opts = {'auth' : ST_AUTH,
                'user' : credential['tenant_id'] + ":" + credential['user_name'],
                'key' : credential['password'],
                'snet' : False,
                'prefix' : '',
                'auth_version' : '1.0'}
            
            try:
                swift.st_delete(opts, container, file)
            except exception.ReddwarfError, e:
                LOG.debug("Fail to delete Swift snapshot instance")
                return wsgi.Result(errors.wrap(errors.Snapshot.SWIFT_DELETE), 500)
        
        try:
            response = snapshot.delete()
        except exception.ReddwarfError, e:
            LOG.debug("Fail to delete DB snapshot instance")
            return wsgi.Result(errors.wrap(errors.Snapshot.DELETE), 500)
        
        # TODO(cp16net): need to set the return code correctly
        LOG.debug("Returning value")              
        return wsgi.Result(None, 204)

    def create(self, req, body, tenant_id):
        """Creates a snapshot."""
        LOG.debug("Snapshots.create() called with %s, %s" % (tenant_id, id))
        LOG.info("Creating a database snapshot for tenant '%s'" % tenant_id)
        LOG.info("req : '%s'\n\n" % req)
        LOG.info("body : '%s'\n\n" % body)

        # Return if instance is not running
        instance_id = body['snapshot']['instanceId']
        try:
            instance = models.GuestStatus().find_by(instance_id=instance_id)
        except exception.ReddwarfError, e:
            LOG.debug("Could not find DB instance in guest_status table: %s" % instance_id)
            return wsgi.Result(errors.wrap(errors.Instance.NOT_FOUND), 404)

        # Return when instance is not in running state
        data = instance.data()
        if not data['state']:
            LOG.debug("The instance %s is not in running state." % instance_id)
            return wsgi.Result(errors.wrap(errors.Instance.INSTANCE_NOT_RUNNING), 403)

        if data['state'] != result_state.ResultState.name(result_state.ResultState.RUNNING):
            LOG.debug("The instance %s is locked for operation in progress." % instance_id)
            return wsgi.Result(errors.wrap(errors.Instance.INSTANCE_LOCKED), 423)

        # Return when a snapshot is being created on the requested instance
        try:
            snapshots = models.Snapshot().find_all(instance_id=instance_id)
            for snapshot in snapshots:
                record = snapshot.data()
                if record['deleted_at'] is None and record['state'] == 'building':
                    LOG.debug("There is a snapshot being created on Instance %s." % instance_id)
                    return wsgi.Result(errors.wrap(errors.Instance.INSTANCE_LOCKED), 423)
        except exception.ReddwarfError, e:
            LOG.debug("Error searching snapshot records: %s" % e)
            pass

        # Start creating snapshot
        context = rd_context.ReddwarfContext(
                          auth_tok=req.headers["X-Auth-Token"],
                          tenant=tenant_id)
        LOG.debug("Context: %s" % context.to_dict())
        
        SWIFT_AUTH_URL = CONFIG.get('reddwarf_proxy_swift_auth_url', 'localhost')
        try:
            credential = models.Credential.find_by(type='object-store')
            LOG.debug("Got credential: %s" % credential)

            snapshot = models.Snapshot().create(name=body['snapshot']['name'],
                                     instance_id=instance_id,
                                     state='building',
                                     user_id=context.user,
                                     tenant_id=context.tenant,
                                     credential=credential['id'])
            LOG.debug("Created snapshot model: %s" % snapshot)
            
            try:
                guest_api.API().create_snapshot(context,
                    instance_id,
                    snapshot['id'],
                    credential,
                    SWIFT_AUTH_URL)
            except exception.ReddwarfError, e:
                LOG.debug("Could not find instance: %s" % id)
                return wsgi.Result(errors.wrap(errors.Instance.NOT_FOUND), 404)
            
            LOG.debug("Maxwell created snapshot")
        except exception.ReddwarfError, e:
            LOG.debug("Error creating snapshot: %s" % e)
            return wsgi.Result(errors.wrap(errors.Snapshot.CREATE), 500)
        
        LOG.debug("Wrote snapshot: %s" % snapshot)
        return wsgi.Result(views.SnapshotView(snapshot, req, tenant_id).create(), 201)
                 

class API(wsgi.Router):
    """API"""
    def __init__(self):
        mapper = routes.Mapper()
        super(API, self).__init__(mapper)
        self._instance_router(mapper)
        self._snapshot_router(mapper)
        #self._admin_router(mapper)
        
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

    def _instance_router(self, mapper):
        instance_resource = InstanceController().create_resource()
        path = "/{tenant_id}/instances"
        #mapper.resource("instance", path, controller=instance_resource)      
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
        
    def _snapshot_router(self, mapper):
        snapshot_resource = SnapshotController().create_resource()
        path = "/{tenant_id}/snapshots"
        #mapper.resource("snapshot", path, controller=snapshot_resource)
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

#    def _admin_router(self, mapper):
#        admin_resource = admin.AdminController().create_resource()
#        mapper.connect("/{tenant_id}/mgmt/{id}/agent",
#                       controller=admin_resource,
#                       action="agent", conditions=dict(method=["POST"]))
#        mapper.connect("/{tenant_id}/mgmt/{id}/messageserver",
#                       controller=admin_resource,
#                       action="message_server", conditions=dict(method=["POST"]))
#        mapper.connect("/{tenant_id}/mgmt/{id}/database",
#                       controller=admin_resource,
#                       action="database", conditions=dict(method=["POST"]))
#        mapper.connect("/{tenant_id}/mgmt/instances",
#                       controller=admin_resource,
#                       action="index_instances", conditions=dict(method=["GET"]))
#        mapper.connect("/{tenant_id}/mgmt/snapshots",
#                       controller=admin_resource,
#                       action="index_snapshots", conditions=dict(method=["GET"])) 
        

def app_factory(global_conf, **local_conf):
    return API()
