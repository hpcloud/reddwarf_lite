# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 Hewlett-Packard Development Company, L.P.
# Copyright 2010-2011 OpenStack LLC.
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

"""Model classes that form the core of instances functionality."""

import logging
import netaddr

from reddwarf import db

from reddwarf.common import config
from reddwarf.common import exception as rd_exceptions
from reddwarf.common import utils
from novaclient.v1_1.client import Client
from novaclient import exceptions as nova_exceptions

CONFIG = config.Config
LOG = logging.getLogger('reddwarf.database.models')


class ModelBase(object):

    _data_fields = []
    _auto_generated_attrs = []

    def _validate(self):
        pass

    def data(self, **options):
        data_fields = self._data_fields + self._auto_generated_attrs
        return dict([(field, self[field]) for field in data_fields])

    def is_valid(self):
        self.errors = {}
#        self._validate_columns_type()
#        self._before_validate()
#        self._validate()
        return self.errors == {}

    def __setitem__(self, key, value):
        setattr(self, key, value)

    def __getitem__(self, key):
        return getattr(self, key)

    def __eq__(self, other):
        if not hasattr(other, 'id'):
            return False
        return type(other) == type(self) and other.id == self.id

    def __ne__(self, other):
        return not self == other

    def __hash__(self):
        return self.id.__hash__()


class RemoteModelBase(ModelBase):

    # This should be set by the remote model during init time
    # The data() method will be using this
    _data_object = None

    @classmethod
    def get_client(cls, credential, region=None):
        # Quite annoying but due to a paste config loading bug.
        # TODO(hub-cap): talk to the openstack-common people about this
        #PROXY_ADMIN_USER = CONFIG.get('reddwarf_proxy_admin_user', 'admin')
        #PROXY_ADMIN_PASS = CONFIG.get('reddwarf_proxy_admin_pass',
        #                              '3de4922d8b6ac5a1aad9')
        #PROXY_ADMIN_TENANT_NAME = CONFIG.get(
        #                                'reddwarf_proxy_admin_tenant_name',
        #                                'admin')
        PROXY_AUTH_URL = CONFIG.get('reddwarf_auth_url',
                                    'http://0.0.0.0:5000/v2.0')

        if region is None:
            region = 'az-2.region-a.geo-1'
        
        try:
            client = Client(credential['user_name'], credential['password'],
                credential['tenant_id'], PROXY_AUTH_URL,
                #proxy_tenant_id=context.tenant,
                #proxy_token=context.auth_tok,
                region_name=region,
                #service_type='compute',
                service_name="Compute")
            client.authenticate()
        except Exception:
            LOG.exception("Error authenticating with Novaclient")
            
        return client

    def data_item(self, data_object):
        data_fields = self._data_fields + self._auto_generated_attrs
        return dict([(field, getattr(data_object, field))
                     for field in data_fields])

    # data magic that will allow for a list of _data_object or a single item
    # if the object is a list, it will turn it into a list of hash's again
    def data(self, **options):
        if self._data_object is None:
            raise LookupError("data object is None")
        if isinstance(self._data_object, list):
            return [self.data_item(item) for item in self._data_object]
        else:
            return self.data_item(self._data_object)


class Instance(RemoteModelBase):

    _data_fields = ['name', 'status', 'id', 'created', 'updated',
                    'flavor', 'links', 'addresses', 'uuid']

    def __init__(self, server=None, credential=None, region=None, uuid=None):
        if server is None and credential is None and uuid is None:
            #TODO(cp16et): what to do now?
            msg = "server, credential, and uuid are not defined"
            raise InvalidModelError(msg)
        elif server is None:
            try:
                self._data_object = self.get_client(credential, region).servers.get(uuid)
            except nova_exceptions.NotFound, e:
                raise rd_exceptions.NotFound(uuid=uuid)
            except nova_exceptions.ClientException, e:
                raise rd_exceptions.ReddwarfError(str(e))
        else:
            self._data_object = server

    @classmethod
    def delete(cls, credential, region, uuid):
        try:
            cls.get_client(credential, region).servers.delete(uuid)
        except nova_exceptions.NotFound, e:
            raise rd_exceptions.NotFound(uuid=uuid)
        except nova_exceptions.ClientException, e:
            raise rd_exceptions.ReddwarfError()

    @classmethod
    def create(cls, credential, region, body, image_id, flavor_id, security_groups, key_name, userdata, files ):
        # self.is_valid()
        instance_name = utils.generate_uuid()
        srv = cls.get_client(credential, region).servers.create(instance_name,
                                                                image_id,
                                                                flavor_id,
                                                                files=files, 
                                                                key_name=key_name, 
                                                                security_groups=security_groups, 
                                                                userdata=userdata)
        return Instance(server=srv)

    @classmethod
    def restart(cls, credential, region, uuid):
        try:
            LOG.debug("Searching for instance using uuid: %s" % uuid)
            cls.get_client(credential, region).servers.reboot(uuid)
        except nova_exceptions.NotFound, e:
            raise rd_exceptions.NotFound(uuid=uuid)
        except nova_exceptions.ClientException, e:
            raise rd_exceptions.ReddwarfError() 


class FloatingIP(RemoteModelBase):

    _data_fields = ['instance_id', 'ip', 'fixed_ip', 'id']

    def __init__(self, floating_ip=None, credential=None, region=None, id=None):
        if id is None and floating_ip is None:
            msg = "id is not defined"
            raise InvalidModelError(msg)
        elif floating_ip is None:
            try:
                self._data_object = self.get_client(credential, region).servers.get(id)
            except nova_exceptions.NotFound, e:
                raise rd_exceptions.NotFound(id=id)
            except nova_exceptions.ClientException, e:
                raise rd_exceptions.ReddwarfError(str(e))
        else:
            self._data_object = floating_ip
            
    @classmethod
    def delete(cls, credential, uuid):
        # TODO implement detach
        pass
    
    @classmethod
    def create(cls, credential, region):
        """Fetches an unassigned IP or creates a new one"""
        ip = None
        client = cls.get_client(credential, region)
        try:
            fl = client.floating_ips.list()
            for flip in fl:
                if flip.instance_id is None:
                    # Choose one of the unassigned IPs
                    ip = flip.ip
                    break
        except nova_exceptions.ClientException, e:
            raise rd_exceptions.ReddwarfError(str(e))
        
        if ip is None:
            try:
                flip = client.floating_ips.create(None)
            except nova_exceptions.ClientException, e:
                print str(e)
                raise rd_exceptions.ReddwarfError(str(e))

        return FloatingIP(floating_ip=flip)

    @classmethod
    def assign(cls, credential, region, floating_ip, server_id):
        """Assigns a floating ip to a server"""
        client = cls.get_client(credential, region)
        try:
            client.servers.add_floating_ip(server_id, floating_ip['ip'])
        except nova_exceptions.ClientException, e:
            raise rd_exceptions.ReddwarfError(str(e))


class Volume(RemoteModelBase):

    _data_fields = ['id', 'attachments', 'size', 'status']
    
    def __init__(self, volume=None, credential=None, region=None, id=None):
        if id is None and volume is None:
            msg = "id is not defined"
            raise InvalidModelError(msg)
        elif volume is None:
            try:
                self._data_object = self.get_client(credential, region).volumes.get(id)
            except nova_exceptions.NotFound, e:
                raise rd_exceptions.NotFound(id=id)
            except nova_exceptions.ClientException, e:
                raise rd_exceptions.ReddwarfError(str(e))
        else:
            self._data_object = volume

    @classmethod
    def create(cls, credential, region, size, display_name):
        """Creates a new Volume"""
        client = cls.get_client(credential, region)
        
        try:
            volume = client.volumes.create(size=size, display_name=display_name)
        except nova_exceptions.ClientException, e:
            LOG.exception('Failed to create remote volume')
            raise rd_exceptions.VolumeCreationFailure(str(e))

        return Volume(volume=volume)
    
    @classmethod
    def attach(cls, credential, region, volume, server_id, device):
        """Assigns a floating ip to a server"""
        client = cls.get_client(credential, region)
        
        # Poll until the volume is attached.
        def volume_is_attached():
            try:
                volume_attachment = client.volumes.create_server_volume(server_id, volume['id'], device)

                from inspect import getmembers
                for name,thing in getmembers(volume):
                    LOG.info(" ----- " + str(name) + " : " + str(thing) )

                return True
            except nova_exceptions.ClientException as e:
                LOG.debug(e)
                return False

        try:
            # Attempt to attach volume
            utils.poll_until(volume_is_attached, sleep_time=5,
                             time_out=int(config.Config.get('volume_attach_time_out', 60)))
            
        except rd_exceptions.PollTimeOut as pto:
            LOG.error("Timeout trying to attach volume: %s" % volume['id'])
            raise rd_exceptions.VolumeAttachmentFailure(str(pto))
        
    @classmethod
    def detach(cls, credential, region, server_id, volume_id):
        try:
            cls.get_client(credential, region).volumes.delete_server_volume(server_id, volume_id)
        except nova_exceptions.NotFound, e:
            raise rd_exceptions.NotFound(uuid=volume_id)
        except nova_exceptions.ClientException, e:
            raise rd_exceptions.ReddwarfError()

    @classmethod
    def delete(cls, credential, region, volume_id):
        try:
            cls.get_client(credential, region).volumes.delete(volume_id)
        except nova_exceptions.NotFound, e:
            raise rd_exceptions.NotFound(uuid=volume_id)
        except nova_exceptions.ClientException, e:
            raise rd_exceptions.ReddwarfError()
        
class Instances(Instance):

    def __init__(self, credential, region):
        self._data_object = self.get_client(credential, region).servers.list()

    def __iter__(self):
        for item in self._data_object:
            yield item


class DatabaseModelBase(ModelBase):
    _auto_generated_attrs = ["id", "created_at"]

    @classmethod
    def create(cls, **values):
        values['id'] = utils.generate_uuid()
        values['created_at'] = utils.utcnow()
#        values['remote_hostname'] = None
#        values['tenant_id'] = "12345"
#        values['availability_zone'] = "1"
        values['deleted'] = False
#        values['updated_at'] = "1"
        instance = cls(**values).save()
#        instance._notify_fields("create")
        return instance

    def save(self):
        if not self.is_valid():
            raise InvalidModelError(self.errors)
#        self._convert_columns_to_proper_type()
#        self._before_save()
        self['updated_at'] = utils.utcnow()
        LOG.debug("Saving %s: %s" % (self.__class__.__name__, self.__dict__))
        return db.db_api.save(self)

    def update(self, **values):
        attrs = utils.exclude(values, *self._auto_generated_attrs)
        self.merge_attributes(attrs)
        result = self.save()
#        self._notify_fields("update")
        return result
    
    def delete(self):
        return self.update(deleted=True, deleted_at=utils.utcnow())   
    
    def __init__(self, **kwargs):
        self.merge_attributes(kwargs)

    def merge_attributes(self, values):
        """dict.update() behavior."""
        for k, v in values.iteritems():
            self[k] = v
            
    @classmethod
    def list(cls):
        return db.db_api.find_all(cls)

    @classmethod
    def find_by(cls, **conditions):
        model = cls.get_by(**conditions)
        if model == None:
            raise ModelNotFoundError(_("%s Not Found") % cls.__name__)
        return model

    @classmethod
    def get_by(cls, **kwargs):
        return db.db_api.find_by(cls, **cls._process_conditions(kwargs))

    @classmethod
    def find_all(cls, **kwargs):
        return db.db_query.find_all(cls, **cls._process_conditions(kwargs))
    
    @classmethod
    def _process_conditions(cls, raw_conditions):
        """Override in inheritors to format/modify any conditions."""
        return raw_conditions


class DBInstance(DatabaseModelBase):
    _data_fields = ['name', 'status', 'remote_id', 'remote_uuid', 'user_id',
                    'tenant_id', 'credential', 'address', 'port', 'flavor', 
                    'remote_hostname', 'availability_zone', 'deleted',
                    'created_at', 'deleted_at']
    

class User(DatabaseModelBase):
    _data_fields = ['name', 'enabled']


class Credential(DatabaseModelBase):
    _data_fields = ['user_name', 'password', 'tenant_id', 'type', 'enabled']
    

class GuestStatus(DatabaseModelBase):
    _data_fields = ['instance_id', 'state', 'deleted', 
                    'deleted_at', 'updated_at']
    
    def guest_statuses_for_instances(self, instance_ids):
        self.find_all(instance_id.in_(instance_id))
        
class ServiceImage(DatabaseModelBase):
    _data_fields = ['service_name', 'image_id', 'tenant_id', 'availability_zone']


class ServiceFlavor(DatabaseModelBase):
    _data_fields = ['service_name', 'flavor_name', 'flavor_id']


class ServiceSecgroup(DatabaseModelBase):
    _data_fields = ['service_name', 'group_name']

class ServiceKeypair(DatabaseModelBase):
    _data_fields = ['service_name', 'key_name']

class ServiceZone(DatabaseModelBase):
    _data_fields = ['service_name', 'tenant_id', 'availability_zone']
    
class Snapshot(DatabaseModelBase):
    _data_fields = ['instance_id', 'name', 'state', 'user_id', 
                    'tenant_id', 'storage_uri', 'credential', 'storage_size',
                    'deleted', 'updated_at', 'deleted_at']
    
    @classmethod
    def list_by_tenant(cls, tenant_id):
        return db.db_api.find_all(cls, **{"tenant_id": tenant_id, "deleted": False})

    @classmethod
    def list_by_instance(cls, instance_id):
        return db.db_api.find_all(cls, **{"instance_id": instance_id, "deleted": False})
    
class Quota(DatabaseModelBase):
    _data_fields = ['tenant_id', 'resource', 'hard_limit']
    
class DBVolume(DatabaseModelBase):
    _data_fields = ['volume_id', 'instance_id', 'size', 'availability_zone']
    
       
def persisted_models():
    return {
        'instance': DBInstance,
        'service_image': ServiceImage,
        'user': User,
        'credential': Credential,
        'guest_status': GuestStatus,
        'service_flavor': ServiceFlavor,
        'snapshot': Snapshot,
        'quota': Quota,
        'service_secgroup': ServiceSecgroup,
        'service_keypair': ServiceKeypair,
        'service_zone': ServiceZone,
        'volume' : DBVolume
        }


class InvalidModelError(rd_exceptions.ReddwarfError):

    message = _("The following values are invalid: %(errors)s")

    def __init__(self, errors, message=None):
        super(InvalidModelError, self).__init__(message, errors=errors)


class ModelNotFoundError(rd_exceptions.ReddwarfError):

    message = _("Not Found")
