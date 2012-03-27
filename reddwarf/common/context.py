# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 Hewlett-Packard Development Company, L.P.
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

"""
Simple class that stores security context information in the web request.

Projects should subclass this class if they wish to enhance the request
context or provide additional information in their specific WSGI pipeline.
"""
import logging

from reddwarf.openstack.common import context
from reddwarf.common import wsgi

LOG = logging.getLogger("reddwarf.common.context")

class ReddwarfContext(context.RequestContext):

    """
    Stores information about the security context under which the user
    accesses the system, as well as additional request information.
    """

    def __init__(self, **kwargs):
        super(ReddwarfContext, self).__init__(**kwargs)

    def to_dict(self):
        return {'user': self.user,
                'tenant': self.tenant,
                'is_admin': self.is_admin,
                'show_deleted': self.show_deleted,
                'read_only': self.read_only,
                'auth_tok': self.auth_tok
                }

    @classmethod
    def from_dict(cls, values):
        return cls(**values)


class ReddwarfContextMiddleware(wsgi.Middleware):
    def __init__(self, app, options):
        self.options = options
        super(ReddwarfContextMiddleware, self).__init__(app)

    def make_context(self, args, **kwargs):
        """
        Create a context with the given arguments.
        """
        #The following headers will be available from Auth filter:
        #'X-Tenant-Id', 'X-Tenant-Name', 'X-User-Id',
        #'X-User-Name', 'X-Roles'
        context_params = {'auth_tok' : args.headers['X-Auth-Token'],
                          'user' : args.headers['X-User-Id'],
                          'tenant' : args.headers['X-Tenant-Id'] }

        LOG.debug("Building context with params: %s" % context_params)
        
        return ReddwarfContext(**context_params)

    def process_request(self, req):
        """
        Extract any authentication information in the request and
        construct an appropriate context from it.
        """
        req.context = self.make_context(req)


def filter_factory(global_conf, **local_conf):
    """
    Factory method for paste.deploy
    """
    conf = global_conf.copy()
    conf.update(local_conf)

    def filter(app):
        return ReddwarfContextMiddleware(app, conf)

    return filter