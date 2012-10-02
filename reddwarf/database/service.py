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
from reddwarf.database import quota
from reddwarf.admin import service as admin
from reddwarf.securitygroup import service as security_group
from reddwarf.securitygroup import models as security_group_models
from reddwarf.database.utils import create_boot_config
from reddwarf.database.utils import file_dict_as_userdata
from reddwarf.database.utils import Sanitizer
from reddwarf.flavor import utils as flavor_utils
from swiftclient import client as swift_client


CONFIG = config.Config
LOG = logging.getLogger(__name__)
Sanitizer = Sanitizer()

class InstanceController(wsgi.Controller):
    """Controller for instance functionality"""
    
    def action(self, req, body, tenant_id, id):
        LOG.info("req : '%s'\n\n" % req)
        LOG.info("Comitting an ACTION again instance %s for tenant '%s'"
                 % (id, tenant_id))
        if not body:
            raise exception.BadRequest(_("Invalid request body."))

        _actions = {
            'restart': self.restart,
            'reset-password': self.reset_password,
            'resize': self._action_resize
            }
        selected_action = None
        for key in body:
            if key in _actions:
                if selected_action is not None:
                    msg = _("Only one action can be specified per request.")
                    raise exception.BadRequest(msg)
                selected_action = _actions[key]
            else:
                msg = _("Invalid instance action: %s") % key
                raise exception.BadRequest(msg)

        if selected_action:
            return selected_action(req, tenant_id, id)
        else:
            raise exception.BadRequest(_("Invalid request body."))

    def _action_resize(self, req, tenant_id, id):
        raise exception.NotImplemented(_("Action resize not implemented"))
    
        
    def index(self, req, tenant_id):
        """Return all instances tied to a particular tenant_id."""
        LOG.debug("Index() called with %s, %s" % (tenant_id, id))  
        # TODO(hub-cap): turn this into middleware
        context = req.context
        LOG.debug("Context: %s" % context.to_dict())
        
        servers = models.DBInstance().find_all(tenant_id=tenant_id, deleted=False)
        LOG.debug(servers)
        
        flavors = models.ServiceFlavor().find_all()
        flavor_list = []
        for flavor in flavors:
            flavor_list.append(flavor)
        LOG.debug(flavor_list)
        
        id_list = []
        for server in servers:
            id_list.append(server['id'])
            server['flavor'] = flavor_list[int(server['flavor'])]['flavor_id']
            
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
        
        # Sanitize id
        if not Sanitizer.whitelist_uuid(id):
            return wsgi.Result(errors.wrap(errors.Input.NONALLOWED_CHARACTERS_ID))
        
        try:
            server = models.DBInstance().find_by(id=id, tenant_id=tenant_id, deleted=False)
        except exception.ReddwarfError, e:
            LOG.exception("Exception occurred when finding instance by id %s" % id)
            return wsgi.Result(errors.wrap(errors.Instance.NOT_FOUND), 404)

        try:
            guest_status = models.GuestStatus().find_by(instance_id=server['id'], deleted=False)
        except exception.ReddwarfError, e:
            LOG.exception("Exception occurred when finding instance guest_status by id %s" % id)
            return wsgi.Result(errors.wrap(errors.Instance.NOT_FOUND), 404)
        
        try:
            flavor = models.ServiceFlavor().find_by(id=server['flavor'], deleted=False)
        except exception.ReddwarfError, e:
            LOG.exception("Exception occurred when finding service flavor for instance id %s" % id)
            return wsgi.Result(errors.wrap(errors.Instance.FLAVOR_NOT_FOUND), 404)

        # Find the security group associated with this server
        try:
            secgroup_association = security_group_models.SecurityGroupInstances().find_by(instance_id=server['id'], deleted=False)
            secgroup = security_group_models.SecurityGroup().find_by(id=secgroup_association['security_group_id'], deleted=False)
        except exception.ModelNotFoundError as e:
            # instances created prior to Security Groups feature will not have a security group
            pass

        # TODO(cp16net): need to set the return code correctly
        LOG.debug("Show() executed correctly")
        return wsgi.Result(views.DBInstanceView(server, guest_status, [secgroup], req, tenant_id, flavor['flavor_id']).show(), 200)

    def delete(self, req, tenant_id, id):
        """Delete a single instance."""
        LOG.debug("Delete() called with %s, %s" % (tenant_id, id))
        # TODO(hub-cap): turn this into middleware
        context = rd_context.ReddwarfContext(
                          auth_tok=req.headers["X-Auth-Token"],
                          tenant=tenant_id)
        
        # Sanitize id
        if not Sanitizer.whitelist_uuid(id):
            return wsgi.Result(errors.wrap(errors.Input.NONALLOWED_CHARACTERS_ID))        
        
        try:
            server = models.DBInstance().find_by(id=id, tenant_id=tenant_id, deleted=False)
        except exception.ReddwarfError, e:
            LOG.exception("Attempting to Delete Instance - Exception occurred finding instance by id %s" % id)
            return wsgi.Result(errors.wrap(errors.Instance.NOT_FOUND), 404)
        
        credential = models.Credential().find_by(id=server['credential'])
        try:
            volume = models.DBVolume().find_by(instance_id=id)
        except exception.ReddwarfError, e:
            volume = None
            LOG.exception("Attempting to Delete Instance - Exception occurred finding volume by instance_id %s, ignore?" % id)

        try:
            self._try_delete_instance(req, context, credential, server, volume)
        except exception.ReddwarfError as e:
            LOG.exception("Failed to delete instance")
            return wsgi.Result(errors.wrap(errors.Instance.REDDWARF_DELETE), 500)

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
        
        try:
            num_instances = self._check_instance_quota(context, 1)
        except exception.QuotaError, e:
            LOG.exception("Quota Error encountered for tenant %s" % tenant_id)
            maximum_instances_allowed = quota.get_tenant_quotas(context, context.tenant)['instances']
            return wsgi.Result(errors.wrap(errors.Instance.QUOTA_EXCEEDED, "You are only allowed to create %s instances on you account." % maximum_instances_allowed), 413)
        
        # Extract any snapshot info from the request
        snapshot = None
        snapshot_support = CONFIG.get('reddwarf_snapshot_support', True)
        if utils.bool_from_string(snapshot_support):
            try:
                snapshot = self._extract_snapshot(body, tenant_id)
            except exception.ReddwarfError, e:
                LOG.exception("Error creating new instance")
                return wsgi.Result(errors.wrap(errors.Snapshot.NOT_FOUND), 500)
            except Exception, e:
                LOG.exception("Error creating new instance")
                return wsgi.Result(errors.wrap(errors.Instance.MALFORMED_BODY), 500)

        # Extract volume size info from the request and check Quota
        try:
            volume_size = self._extract_volume_size(body)
            if volume_size is None:
                volume_size = config.Config.get('default_volume_size', 20)
            
            self._check_volume_size_quota(context, volume_size)
        except exception.BadValue, e:
            LOG.exception("Bad value for volume size")
            return wsgi.Result(errors.wrap(errors.Instance.MALFORMED_BODY, 'Invalid volume size'), 400)
        except exception.QuotaError, e:
            LOG.exception("Unable to allocate volume, Volume Size Quota has been exceeded")
            maximum_snapshots_allowed = quota.get_tenant_quotas(context, context.tenant)['volume_space']
            return wsgi.Result(errors.wrap(errors.Instance.VOLUME_QUOTA_EXCEEDED, "You are only allowed to allocate %s GBs of Volume Space for your account." % maximum_snapshots_allowed), 413)
        except exception.ReddwarfError, e:
            LOG.exception()
            return wsgi.Result(errors.wrap(errors.Instance.REDDWARF_CREATE), 500)
        
        # Extract flavor info from the request
        try:
            flavor_ref = body['instance']['flavorRef']
        except KeyError, e:
            LOG.info("The body does not contain an [instance][flavorRef] key - using default flavor of medium")
            try:
                flavor_model = models.ServiceFlavor.find_by(service_name="database", flavor_name='large', deleted=False)
            except:
                LOG.exception("The ServiceFlavor table doesn't contain a default flavor named 'medium'!")
                return wsgi.Result(errors.wrap(errors.Instance.FLAVOR_NOT_FOUND_CREATE), 404)
            flavor_ref = flavor_utils.build_flavor_href(req, tenant_id, flavor_model['flavor_id'])
        
        # Validate the request
        try:
            flavor_id = utils.get_id_from_href(flavor_ref)
            #if not Sanitizer.whitelist_uuid(flavor_id):
            #TODO: (joshdorothy) we need to implement some sort of href sanitizer if we're 
            #  going to be accepting them in a request body    
            LOG.debug("retrieved flavor id %s from flavor ref %s" % (flavor_id, flavor_ref))
        except:
            LOG.exception("Could not parse %s" % flavor_ref)
            return wsgi.Result(errors.wrap(errors.Instance.MALFORMED_BODY), 500)
                    
            
        # Fetch all boot parameters from Database
        try:
            image_id, flavor, keypair_name, region_az, credential = self._load_boot_params(tenant_id, flavor_id)
        except exception.ModelNotFoundError:
            return wsgi.Result(errors.wrap(errors.Instance.FLAVOR_NOT_FOUND_CREATE), 404)

        password = utils.generate_password()
        
        
        
        try:
            secgroup = self._try_create_security_group(req, context, body['instance']['name'], 3306)
            db_secgroup = security_group_models.SecurityGroup().find_by(id=secgroup['security_group']['id'], deleted=False)
            
            remote_secgroups = [db_secgroup['remote_secgroup_name']]
            
            instance, guest_status, file_dict = self._try_create_server(context, 
                                                                        body, 
                                                                        credential, 
                                                                        region_az, 
                                                                        remote_secgroups, 
                                                                        keypair_name, 
                                                                        image_id, 
                                                                        flavor, 
                                                                        snapshot, 
                                                                        password)
        except exception.SecurityGroupCreationFailure, e:
            LOG.exception("Error creating DBaaS Instance")
            return wsgi.Result(errors.wrap(errors.Instance.REDDWARF_CREATE, "Instance creation failure"), 500)
        except exception.ReddwarfError, e:
            if "RAMLimitExceeded" in e.message:
                LOG.error("Remote Nova Quota exceeded on create instance: %s" % e.message)
                return wsgi.Result(errors.wrap(errors.Instance.RAM_QUOTA_EXCEEDED), 500)
            else:
                LOG.exception("Error creating DBaaS instance")
                #Cleanup
                try:
                    if secgroup is not None:
                        secgroup = security_group.SecurityGroupController().delete(req, context.tenant, secgroup['security_group']['id'])
                except exception.SecurityGroupDeletionFailure, e:
                    LOG.error("Failed to delete Security Group after Instance Creation Failure. Ignoring..")
                    
                return wsgi.Result(errors.wrap(errors.Instance.REDDWARF_CREATE, "Instance creation failure"), 500)
        else:
            # Associate Security group to Instance
            security_group_models.SecurityGroupInstances().create(security_group_id=secgroup['security_group']['id'],
                                                                  instance_id=instance['id'])
            
        # Attempt to attach a volume    
        try:
            self._try_attach_volume(context, body, credential, region_az, volume_size, instance)
        except exception.ReddwarfError, e:
            LOG.exception("Error creating DBaaS instance - volume attachment failed")
            return wsgi.Result(errors.wrap(errors.Instance.REDDWARF_CREATE, "Volume Attachment failure"), 500)
        
        # Invoke worker to ensure instance gets created
        worker_api.API().ensure_create_instance(None, instance, file_dict_as_userdata(file_dict))
        
        return wsgi.Result(views.DBInstanceView(instance, guest_status, [db_secgroup], req, tenant_id, flavor['flavor_id']).create('dbas', password), 201)


    def restart(self, req, tenant_id, id):
        """Restart an instance."""
        LOG.debug("Called restart() with %s, %s" % (tenant_id, id))
        context = rd_context.ReddwarfContext(
                          auth_tok=req.headers["X-Auth-Token"],
                          tenant=tenant_id)        

        # Sanitize id
        if not Sanitizer.whitelist_uuid(id):
            return wsgi.Result(errors.wrap(errors.Input.NONALLOWED_CHARACTERS_ID))  

        try:
            instance = models.DBInstance().find_by(id=id)
        except exception.ReddwarfError, e:
            LOG.error("Could not find db instance %s to restart" % id)
            return wsgi.Result(errors.wrap(errors.Instance.NOT_FOUND), 404)

        # Make sure the guest instance is in running state
        try:
            guest = models.GuestStatus().find_by(instance_id=id)
        except exception.ReddwarfError, e:
            LOG.error("Could not find DB guest_status for instance id: %s" % id)
            return wsgi.Result(errors.wrap(errors.Instance.NOT_FOUND), 404)

        guest_data = guest.data()
        if not guest_data['state']:
            LOG.error("Unable to restart, the instance %s is not in running state." % id)
            return wsgi.Result(errors.wrap(errors.Instance.INSTANCE_NOT_RUNNING), 403)

        if guest_data['state'] != result_state.ResultState.name(result_state.ResultState.RUNNING):
            LOG.error("The instance %s is locked due to operation in progress." % id)
            return wsgi.Result(errors.wrap(errors.Instance.INSTANCE_LOCKED), 423)

        instance_data = instance.data()
        region_az = instance_data['availability_zone']
        if region_az is None:
            region_az = CONFIG.get('reddwarf_proxy_default_region', 'az-2.region-a.geo-1')

        
        credential = models.Credential().find_by(id=instance_data['credential'])
        try:
            models.Instance.restart(credential, region_az, instance_data['remote_uuid'])
        except exception.ReddwarfError, e:
            LOG.exception("Could not restart remote instance: %s" % instance_data['remote_id'])
            return wsgi.Result(errors.wrap(errors.Instance.RESTART), 500)

        guest.update(state=result_state.ResultState.name(result_state.ResultState.RESTARTING))
        return wsgi.Result(None, 204)


    def reset_password(self, req, tenant_id, id):
        """Resets DB password on remote instance"""
        LOG.info("Resets DB password on Instance %s", id)
        LOG.debug("Req.environ: %s" % req.environ)

        # Sanitize id
        if not Sanitizer.whitelist_uuid(id):
            return wsgi.Result(errors.wrap(errors.Input.NONALLOWED_CHARACTERS_ID))  

        # Return if instance is not found
        try:
            instance = models.GuestStatus().find_by(instance_id=id)
        except exception.ReddwarfError, e:
            LOG.error("Could not find DB instance in guest_status table: %s" % id)
            return wsgi.Result(errors.wrap(errors.Instance.NOT_FOUND), 404)

        # Return when instance is not in running state
        data = instance.data()
        if not data['state']:
            LOG.error("Unable to reset password, the instance %s is not in running state." % id)
            return wsgi.Result(errors.wrap(errors.Instance.INSTANCE_NOT_RUNNING), 403)

        if data['state'] != result_state.ResultState.name(result_state.ResultState.RUNNING):
            LOG.error("Unable to reset password, the instance %s is locked for operation in progress." % id)
            return wsgi.Result(errors.wrap(errors.Instance.INSTANCE_LOCKED), 423)

        # Generate password
        password = utils.generate_password()
        context = rd_context.ReddwarfContext(
                          auth_tok=req.headers["X-Auth-Token"],
                          tenant=tenant_id)

        # Dispatch the job to Smart Agent
        try:
            result = guest_api.API().reset_password(context, id, password)
        except exception.NotFound as nf:
            LOG.exception("unable to reset password for instance: %s" % id)
            return wsgi.Result(errors.wrap(errors.Instance.NOT_FOUND), 404)
        except exception.ReddwarfError as e:
            LOG.exception("Smart Agent failed to reset password.")
            return wsgi.Result(errors.wrap(errors.Instance.RESET_PASSWORD), 500)
        
        # Return response
        if result == result_state.ResultState.SUCCESS:
            return wsgi.Result({'password': password}, 200)
        else:
            LOG.error("Smart Agent failed to reset password (RPC response: '%s')." % result)
            return wsgi.Result(errors.wrap(errors.Instance.RESET_PASSWORD), 500)


    def _try_create_server(self, context, body, credential, region, sec_groups, keypair, image_id, flavor, snapshot=None, password=None):
        """Create remote Server """
        # Create DB Instance record
        try:
            instance = models.DBInstance().create(name=body['instance']['name'],
                                     status='building',
                                     user_id=context.user,
                                     tenant_id=context.tenant,
                                     credential=credential['id'],
                                     port='3306',
                                     flavor=flavor['id'],
                                     availability_zone=region)

            LOG.debug("Wrote DB Instance: %s" % instance)

            guest_status = models.GuestStatus().create(instance_id=instance['id'], state='scheduling')
        
        except exception.ReddwarfError, e:
            LOG.exception("Error creating DB Instance record")
            raise e

        try:
            sec_group = ['dbaas-instance']
            sec_group.extend(sec_groups)

            file_dict = self._create_boot_config_file(snapshot, password)
            LOG.debug('%s',file_dict)

            userdata = file_dict_as_userdata(file_dict)

            server = models.Instance.create(credential, region, body, image_id, flavor['flavor_id'],
                                            security_groups=sec_group, key_name=keypair,
                                            userdata=userdata, files=None).data()
            
            if not server:
                raise exception.ReddwarfError(errors.Instance.REDDWARF_CREATE)
            else:
                # update instance and guest_status
                instance.update(remote_id=server['id'],
                                remote_uuid=server['uuid'],
                                remote_hostname=server['name'])
                
                guest_status.update(state='building')
                

            LOG.debug("Wrote remote server: %s" % server)
            
        except (Exception) as e:
            LOG.exception("Error attempting to create a remote Server")
            raise exception.ReddwarfError(e)

        return instance, guest_status, file_dict


    def _try_attach_volume(self, context, body, credential, region, volume_size, instance):
        
        volume_support = CONFIG.get('reddwarf_volume_support', 'False')
        if not utils.bool_from_string(volume_support):
            # Do nothing if volume-support is not enabled
            return

        # Create the remote volume and a DB Volume record
        try:
            volume = models.Volume.create(credential, region, volume_size, 'mysql-%s' % instance['remote_id']).data()
        except Exception as e:
            LOG.exception("Failed to create a remote volume of size %s" % volume_size)
            raise exception.VolumeCreationFailure(e)
        else:
            LOG.debug("Created remote volume %s of size %s" % (volume['id'], volume_size))
            try:
                db_volume = models.DBVolume().create(volume_id=volume['id'],
                                                     size=volume_size,
                                                     availability_zone=region,
                                                     instance_id="TBD",
                                                     tenant_id=context.tenant)
                
            except Exception as e:
                LOG.exception("Failed to write DB Volume record for instance volume")
                raise exception.ReddwarfError(e)

        # Attempt to attach the volume to an instance        
        try:
            device_name = config.Config.get('volume_device_name', '/dev/vdc')
            models.Volume.attach(credential, region, volume, instance['remote_id'], device_name)
        except Exception as e:
            LOG.exception("Failed to attach volume %s with instance remote_id %s" % (volume['id'], instance['remote_id']))
            
            # Failed to attach the volume delete the volume
            try:
                models.Volume.delete(credential, region, volume['id'])
            except exception.NotFound as e:
                # volume not found, ok
                pass
            except exception.ReddwarfError as e:
                LOG.exception("Failed to delete volume after attachment failure")
            else:
                # Delete the DB volume record as well
                db_volume.delete()
            
            raise exception.VolumeAttachmentFailure(e)
        else:
            LOG.debug("Attached volume %s to instance %s" % (volume['id'], instance['remote_id']))        
            try:
                db_volume.update(instance_id=instance['id'])
            except Exception as e:
                LOG.exception("Failed to update DB Volume with instance id")
                raise exception.ReddwarfError(e)

    def _try_delete_instance(self, req, context, credential, server, db_volume):
        
        remote_uuid = server["remote_uuid"]
        region_az = server['availability_zone']
        if region_az is None:
            region_az = CONFIG.get('reddwarf_proxy_default_region', 'az-2.region-a.geo-1')
            
        # Try to delete the Nova instance
        remote_server_deleted = False
        try:
            LOG.debug("Deleting remote instance with id %s" % remote_uuid)
            # request Nova to delete the instance
            models.Instance.delete(credential, region_az, remote_uuid)
            remote_server_deleted = True
        except exception.NotFound:
            LOG.warn("Deleting Non-Existant Remote instance")
            remote_server_deleted = True
        except exception.ReddwarfError as e:
            LOG.exception("Failed Deleting Remote instance")
            raise e

        if remote_server_deleted:
            if db_volume is not None:
                # Attempt to delete the volume
                try:
                    models.Volume.delete(credential, region_az, db_volume['volume_id'])
                except exception.NotFound as e:
                    LOG.debug("Could not delete remote volume with id %s, may already be deleted" % db_volume['volume_id'])
                    pass
                except exception.VolumeDeletionFailure as e:
                    LOG.error("Failed to delete remote volume with id %s" % db_volume['volume_id'])
                    raise e
                
                # Delete the DB Volume Record
                try:
                    db_volume = db_volume.delete()
                except exception.ReddwarfError, e:
                    LOG.exception("Failed to Delete DB Volume record")
                    raise e
            
            # Attempt to delete the Associated security group
            association_count = security_group_models.SecurityGroupInstances().find_all(instance_id=server['id'], deleted=False).count()
            if association_count > 1:
                LOG.error("Security group associated to more than 1 instance.  This should not be possible.")
            else:
                try:
                    # Find the Association
                    sec_group = security_group_models.SecurityGroupInstances().find_by(instance_id=server['id'], deleted=False)
                    security_group.SecurityGroupController().delete(req, context.tenant, sec_group['security_group_id'])
                    sec_group.delete()
                except exception.ModelNotFoundError as e:
                    pass
                    # This shouldn't happen, but ignore if we don't have a security group to delete
                
            # Try to delete the Reddwarf lite instance
            try:
                server = server.delete()
            except exception.ReddwarfError, e:
                LOG.exception("Failed to Delete DB Instance record")
                raise e
            
            # Finally, try to delete the associated GuestStatus record
            try:
                guest_status = models.GuestStatus().find_by(instance_id=server['id'])
                guest_status.delete()
            except exception.ReddwarfError, e:
                LOG.exception("Failed to Delete GuestStatus record")
                raise e
        else:
            raise exception.ReddwarfError("Failed to delete instance")

    def _try_create_security_group(self, req, context, instance_name, port):
        security_group_name = "default_" % instance_name
        secgroup_req_body = { "security_group" : { "name" : security_group_name, "description" : "Default DBaaS Security Group" } }
        
        secgroup = security_group.SecurityGroupController().create(req, secgroup_req_body, context.tenant)
        secgroup_json = secgroup.data('application/json')
        
        try:
            rule_req_body = { 
                              "security_group_rule" : {
                                "security_group_id" : secgroup_json['security_group']['id'],
                                "cidr" : "15.0.0.0/0",
                                "from_port" : port,
                                "to_port" : port
                              }
                            }
            
            security_group.SecurityGroupRuleController().create(req, rule_req_body, context.tenant)

        except exception.ReddwarfError, e:
            LOG.exception("Failed creating a security group rule, deleting security group")
            security_group.SecurityGroupController().delete(req, context.tenant, secgroup_json['security_group']['id'])
            raise e
        
        return secgroup_json


    def _extract_snapshot(self, body, tenant_id):

        if 'instance' not in body:
            LOG.error("The body passed to create was malformed")
            raise Exception

        if 'snapshotId' in body['instance']:
            snapshot_id = body['instance']['snapshotId']
            if snapshot_id:
                if not Sanitizer.whitelist_uuid(snapshot_id):
                    return wsgi.Result(errors.wrap(errors.Input.NONALLOWED_CHARACTERS_ID)) 
                try:
                    snapshot = models.Snapshot().find_by(id=snapshot_id, tenant_id=tenant_id, deleted=False)
                    return snapshot
                except exception.ReddwarfError, e:
                    LOG.error("Error finding snapshot to create new instance with - Snapshot Record with id %s not found" % snapshot_id)
                    raise e

    def _extract_volume_size(self, body):
        volume_size = None
        
        if body['instance'].get('volume', None) is not None:
            try:
                volume_size = int(body['instance']['volume']['size'])
            except ValueError as e:
                return wsgi.Result(errors.wrap(errors.Input.NONINTEGER_VOLUME_SIZE))
            
        return volume_size
        
        
    def _load_boot_params(self, tenant_id, flavor_id):
        try:
            service_zone = models.ServiceZone.find_by(service_name='database', tenant_id=tenant_id, deleted=False)
        except exception.ModelNotFoundError, e:
            LOG.info("Service Zone for tenant %s not found, using zone for 'default_tenant'" % tenant_id)
            service_zone = models.ServiceZone.find_by(service_name='database', tenant_id='default_tenant', deleted=False)

        region_az = service_zone['availability_zone']

        # Attempt to find Boot parameters for a specific tenant
        try:
            service_image = models.ServiceImage.find_by(service_name="database", tenant_id=tenant_id, availability_zone=region_az, deleted=False)
        except exception.ModelNotFoundError, e:
            LOG.info("Service Image for tenant %s not found, using image for 'default_tenant'" % tenant_id)
            service_image = models.ServiceImage.find_by(service_name="database", tenant_id='default_tenant', availability_zone=region_az, deleted=False)

        image_id = service_image['image_id']
        
        # Check to see if flavor exists
        try:
            flavor = models.ServiceFlavor.find_by(service_name="database", flavor_id=flavor_id, deleted=False)
            LOG.debug("Searching by flavor id %s, found service flavor id %s" % (flavor_id, flavor['id']))
        except exception.ModelNotFoundError, e:
            LOG.exception("Error finding service flavor %s in database" % flavor_id)
            raise e
        
        service_keypair = models.ServiceKeypair.find_by(service_name='database', deleted=False)
        keypair_name = service_keypair['key_name']
        
        # Get the credential to use for proxy compute resource
        credential = models.Credential.find_by(type='compute', deleted=False)
        
        LOG.debug("Using ImageID %s" % image_id)
        LOG.debug("Using FlavorID %s" % flavor['flavor_id'])
        LOG.debug("Using Keypair %s" % keypair_name)
        LOG.debug("Using Region %s" % region_az)
        
        return (image_id, flavor, keypair_name, region_az, credential)
        
    def _create_boot_config_file(self, snapshot, password):
        """Creates a config file that gets placed in the instance
        for the Agent to configure itself"""
        
        if snapshot:
            storage_uri = snapshot['storage_uri']
            config = create_boot_config(CONFIG,
                                        models.Credential().find_by(id=snapshot['credential']),
                                        storage_uri,
                                        password)
        else:
            storage_uri = None
            config = create_boot_config(CONFIG, None, storage_uri, password)
        return { '/home/nova/agent.config': config }

    def _check_instance_quota(self, context, count=1):
        num_instances = quota.allowed_instances(context, count)
        LOG.debug('number of instances allowed to create %s' % num_instances)
        if num_instances < count:
            tid = context.tenant
            if num_instances <= 0:
                msg = _("Cannot create any more instances of this type.")
            else:
                msg = (_("Can only create %s more instances of this type.") %
                       num_instances)
            LOG.warn(_("Quota exceeded for %(tid)s,"
                  " tried to create %(count)s instances. %(msg)s"), locals())
            
            raise exception.QuotaError("InstanceLimitExceeded")

        return num_instances
    
    def _check_volume_size_quota(self, context, requested_size=1):
        allowed_volume_size = quota.allowed_volume_size(context, requested_size)
        LOG.debug('size of volume allowed to create %s' % allowed_volume_size)
        if allowed_volume_size < requested_size:
            tid = context.tenant
            if allowed_volume_size <= 0:
                msg = _("Cannot allocated any more volume space.")
            else:
                msg = (_("Can only allocated %s more space for volumes.") %
                       allowed_volume_size)
            LOG.warn(_("Quota exceeded for %(tid)s,"
                  " tried to allocate %(requested_size)s volume space. %(msg)s"), locals())
            
            raise exception.QuotaError("VolumeSizeLimitExceeded")

        return allowed_volume_size
        
    def get_guest_state_mapping(self, id_list):
        """Returns a dictionary of guest statuses keyed by guest ids."""
        results = db.db_api.find_guest_statuses_for_instances(id_list)
        return dict([(r.instance_id, r) for r in results])
    

class SnapshotController(wsgi.Controller):
    """Controller for snapshot functionality"""

    def show(self, req, tenant_id, id):
        """Return information about a specific snapshot."""
        LOG.debug("Snapshots.show() called with %s, %s" % (tenant_id, id))
        LOG.debug("Showing all snapshots")
        
        # Sanitize id
        if not Sanitizer.whitelist_uuid(id):
            return wsgi.Result(errors.wrap(errors.Input.NONALLOWED_CHARACTERS_ID))        
        
#        context = rd_context.ReddwarfContext(
#                          auth_tok=req.headers["X-Auth-Token"],
#                          tenant=tenant_id)
#        LOG.debug("Context: %s" % context.to_dict())
        try:
            snapshot = models.Snapshot().find_by(id=id, deleted=False)
        except exception.ReddwarfError, e:            
            LOG.exception("Snapshot Show() failed with an exception")
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
        LOG.info("Snapshots delete() called with %s, %s" % (tenant_id, id))
        LOG.debug("Deleting snapshot")
        
        context = rd_context.ReddwarfContext(
                          auth_tok=req.headers["X-Auth-Token"],
                          tenant=tenant_id)
        LOG.debug("Delete() context") 
        
        # Sanitize id
        if not Sanitizer.whitelist_uuid(id):
            return wsgi.Result(errors.wrap(errors.Input.NONALLOWED_CHARACTERS_ID))          
        
        snapshot = None
        try:
            snapshot = models.Snapshot().find_by(id=id)
        except exception.ReddwarfError, e:
            LOG.exception("Failed to find snapshot with id %s to delete" % id)
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
                connection = self._get_swift_connection(opts)
                connection.delete_object(container, file)
            except Exception, e:
                if "404" in "%s" % e:
                    LOG.exception("Snapshot not found: %s" % e)
                    return wsgi.Result(errors.wrap(errors.Snapshot.NOT_FOUND), 404)
                
                LOG.exception("Fail to delete snapshot from Swift: %s" % e)
                return wsgi.Result(errors.wrap(errors.Snapshot.SWIFT_DELETE), 500)
        
        try:
            response = snapshot.delete()
        except exception.ReddwarfError, e:
            LOG.exception("Failed to delete DB snapshot record")
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

        snapshot_support = CONFIG.get('reddwarf_snapshot_support', True)
        if not utils.bool_from_string(snapshot_support):
            raise exception.NotImplemented("This resource is temporarily not available")

        # Return if instance is not running
        try:
            instance_id = body['snapshot']['instanceId']
        except exception.ReddwarfError, e:
            LOG.exception("body['snapshot']['instanceId'] does not exist")
            return wsgi.Result(errors.wrap(errors.Snapshot.NO_BODY_INSTANCE_ID))
        
        # Sanitize instance_id
        if not Sanitizer.whitelist_uuid(instance_id):
            return wsgi.Result(errors.wrap(errors.Input.NONALLOWED_CHARACTERS_INSTANCE_ID))          
        
        try:
            guest_status = models.GuestStatus().find_by(instance_id=instance_id)
        except exception.ReddwarfError, e:
            LOG.error("Could not find DB instance in guest_status table: %s" % instance_id)
            return wsgi.Result(errors.wrap(errors.Instance.NOT_FOUND), 404)

        # Return when instance is not in running state
        if not guest_status['state']:
            LOG.error("Unable to create Snapshot, the instance %s is not in running state." % instance_id)
            return wsgi.Result(errors.wrap(errors.Instance.INSTANCE_NOT_RUNNING), 403)

        if guest_status['state'] != result_state.ResultState.name(result_state.ResultState.RUNNING):
            LOG.error("Unable to create snapshot, the instance %s is locked for operation in progress." % instance_id)
            return wsgi.Result(errors.wrap(errors.Instance.INSTANCE_LOCKED), 423)

        # Return when a snapshot is being created on the requested instance
        try:
            snapshots = models.Snapshot().find_all(instance_id=instance_id)
            for snapshot in snapshots:
                if snapshot['deleted_at'] is None and snapshot['state'] == 'building':
                    LOG.error("Unable to create snapshot, There is already a snapshot being created on Instance %s." % instance_id)
                    return wsgi.Result(errors.wrap(errors.Instance.INSTANCE_LOCKED), 423)
        except exception.ReddwarfError, e:
            LOG.exception("Error searching snapshot records: %s" % e)
            pass

        # Start creating snapshot
        # TODO (vipulsabhaya) obtain context from request
        context = rd_context.ReddwarfContext(
                          auth_tok=req.headers["X-Auth-Token"],
                          tenant=tenant_id)
        
        LOG.debug("Context: %s" % context.to_dict())

        # Return if quota for snapshots has been reached
        try:
            num_snapshots = self._check_snapshot_quota(context, 1)
        except exception.QuotaError, e:
            LOG.error("Unable to create snapshot, Snapshot Quota has been exceeded")
            maximum_snapshots_allowed = quota.get_tenant_quotas(context, context.tenant)['snapshots']
            return wsgi.Result(errors.wrap(errors.Snapshot.QUOTA_EXCEEDED, "You are only allowed to create %s snapshots for you account." % maximum_snapshots_allowed), 413)
        
        SWIFT_AUTH_URL = CONFIG.get('reddwarf_proxy_swift_auth_url', 'localhost')
        
        try:
            name = body['snapshot']['name']
        except exception.ReddwarfError, e:
            LOG.exception("body['snapshot']['name'] does not exist")
            return wsgi.Result(errors.wrap(errors.Snapshot.NO_BODY_NAME))
        
        try:
            credential = models.Credential.find_by(type='object-store')
            LOG.debug("Got credential: %s" % credential)

            snapshot = models.Snapshot().create(name=name,
                                     instance_id=instance_id,
                                     state='building',
                                     user_id=context.user,
                                     tenant_id=context.tenant,
                                     credential=credential['id'])
            LOG.debug("Created snapshot model: %s" % snapshot)
            
            try:
                snapshot_key = CONFIG.get('snapshot_key', 'changeme')
                guest_api.API().create_snapshot(context,
                    instance_id,
                    snapshot['id'],
                    credential,
                    SWIFT_AUTH_URL,
                    snapshot_key)
            except exception.ReddwarfError, e:
                LOG.exception("Could not create snapshot: %s" % id)
                return wsgi.Result(errors.wrap(errors.Instance.NOT_FOUND), 404)
            
            LOG.debug("Maxwell created snapshot")
        except exception.ReddwarfError, e:
            LOG.exception("Error creating snapshot: %s" % e)
            return wsgi.Result(errors.wrap(errors.Snapshot.CREATE), 500)
        
        LOG.debug("Wrote snapshot: %s" % snapshot)
        return wsgi.Result(views.SnapshotView(snapshot, req, tenant_id).create(), 201)
              
    def _check_snapshot_quota(self, context, count=1):
        num_snapshots = quota.allowed_snapshots(context, count)
        LOG.debug('number of snapshots allowed to create %s' % num_snapshots)
        if num_snapshots < count:
            tid = context.tenant
            if num_snapshots <= 0:
                msg = _("Cannot create any more snapshots of this type.")
            else:
                msg = (_("Can only create %s more snapshots of this type.") %
                       num_snapshots)
            LOG.warn(_("Quota exceeded for %(tid)s,"
                  " tried to create %(count)s snapshots. %(msg)s"), locals())
            
            raise exception.QuotaError("InstanceLimitExceeded")

        return num_snapshots
   
    def _get_swift_connection(self, options):
        return swift_client.Connection(options['auth'],
                                      options['user'],
                                      options['key'],
                                      options['snet'],
                                      auth_version=options['auth_version'])
