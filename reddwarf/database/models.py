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
    def get_client(cls, context):
        # Quite annoying but due to a paste config loading bug.
        # TODO(hub-cap): talk to the openstack-common people about this
        PROXY_ADMIN_USER = CONFIG.get('reddwarf_proxy_admin_user', 'admin')
        PROXY_ADMIN_PASS = CONFIG.get('reddwarf_proxy_admin_pass',
                                      '3de4922d8b6ac5a1aad9')
        PROXY_ADMIN_TENANT_NAME = CONFIG.get(
                                        'reddwarf_proxy_admin_tenant_name',
                                        'admin')
        PROXY_AUTH_URL = CONFIG.get('reddwarf_auth_url',
                                    'http://0.0.0.0:5000/v2.0')
        print PROXY_AUTH_URL
        client = Client(PROXY_ADMIN_USER, PROXY_ADMIN_PASS,
            PROXY_ADMIN_TENANT_NAME, PROXY_AUTH_URL,
            #proxy_tenant_id=context.tenant,
            #proxy_token=context.auth_tok,
            region_name='az-2.region-a.geo-1',
            #service_type='compute',
            service_name="Compute")
        client.authenticate()
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

    def __init__(self, server=None, context=None, uuid=None):
        if server is None and context is None and uuid is None:
            #TODO(cp16et): what to do now?
            msg = "server, content, and uuid are not defined"
            raise InvalidModelError(msg)
        elif server is None:
            try:
                self._data_object = self.get_client(context).servers.get(uuid)
            except nova_exceptions.NotFound, e:
                raise rd_exceptions.NotFound(uuid=uuid)
            except nova_exceptions.ClientException, e:
                raise rd_exceptions.ReddwarfError(str(e))
        else:
            self._data_object = server

    @classmethod
    def delete(cls, context, uuid):
        try:
            cls.get_client(context).servers.delete(uuid)
        except nova_exceptions.NotFound, e:
            raise rd_exceptions.NotFound(uuid=uuid)
        except nova_exceptions.ClientException, e:
            raise rd_exceptions.ReddwarfError()

    @classmethod
    def create(cls, context, body, image_id, flavor_id, security_groups, key_name, userdata, files ):
        # self.is_valid()
        LOG.info("instance body : '%s'\n\n" % body)
        flavorRef = body['instance']['flavorRef']
        srv = cls.get_client(context).servers.create(body['instance']['name'],
                                                     image_id,
                                                     flavorRef,
                                                     files=files, 
                                                     key_name=key_name, 
                                                     security_groups=security_groups, 
                                                     userdata=userdata)
        return Instance(server=srv)


class Instances(Instance):

    def __init__(self, context):
        self._data_object = self.get_client(context).servers.list()

    def __iter__(self):
        for item in self._data_object:
            yield item


class DatabaseModelBase(ModelBase):
    _auto_generated_attrs = ["id", "created_at", "updated_at", "deleted_at"]

    @classmethod
    def create(cls, **values):
        values['id'] = utils.generate_uuid()
        values['created_at'] = utils.utcnow()
#        values['remote_hostname'] = None
#        values['tenant_id'] = "12345"
#        values['availability_zone'] = "1"
#        values['deleted'] = "0"
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
        return self.update(deleted=True)
    
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
        LOG.debug("CLS: %s" % conditions)
        model = cls.get_by(**conditions)
        if model == None:
            raise ModelNotFoundError(_("%s Not Found") % cls.__name__)
        return model

    @classmethod
    def get_by(cls, **kwargs):
        return db.db_api.find_by(cls, **cls._process_conditions(kwargs))

    @classmethod
    def _process_conditions(cls, raw_conditions):
        """Override in inheritors to format/modify any conditions."""
        return raw_conditions


class DBInstance(DatabaseModelBase):
    _data_fields = ['name', 'status', 'remote_id', 'remote_uuid', 'user_id',
                    'tenant_id', 'credential', 'address', 'port', 'flavor', 
                    'remote_hostname', 'availability_zone', 'deleted', 'links']
    

class User(DatabaseModelBase):
    _data_fields = ['name', 'enabled']


class Credential(DatabaseModelBase):
    _data_fields = ['user_name', 'password', 'tenant_id', 'type', 'enabled']
    

class GuestStatus(DatabaseModelBase):
    _data_fields = ['instance_id', 'state', 'deleted']
    

class ServiceImage(DatabaseModelBase):
    _data_fields = ['service_name', 'image_id']


class ServiceFlavor(DatabaseModelBase):
    _data_fields = ['service_name', 'flavor_name', 'flavor_id']


class Snapshot(DatabaseModelBase):
    _data_fields = ['instance_id', 'name', 'state', 'user_id', 
                    'tenant_id', 'storage_uri', 'credential', 'storage_size',
                    'deleted']
    
    @classmethod
    def list_by_tenant(cls, tenant_id):
        return db.db_api.find_all(cls, **{"tenant_id": tenant_id})

    @classmethod
    def list_by_instance(cls, instance_id):
        return db.db_api.find_all(cls, **{"instance_id": instance_id})
    
class Quota(DatabaseModelBase):
    _data_fields = ['tenant_id', 'resource', 'hard_limit']
    
        
def persisted_models():
    return {
        'instance': DBInstance,
        'service_image': ServiceImage,
        'user': User,
        'credential': Credential,
        'guest_status': GuestStatus,
        'service_flavor': ServiceFlavor,
        'snapshot': Snapshot,
        'quota': Quota
        }


class InvalidModelError(rd_exceptions.ReddwarfError):

    message = _("The following values are invalid: %(errors)s")

    def __init__(self, errors, message=None):
        super(InvalidModelError, self).__init__(message, errors=errors)


class ModelNotFoundError(rd_exceptions.ReddwarfError):

    message = _("Not Found")
