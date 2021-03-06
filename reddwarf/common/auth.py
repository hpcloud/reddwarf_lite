# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright 2012 Hewlett-Packard Development Company, L.P.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#  WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
###########################################################################
#
# Copyright (c) 2010-2011 OpenStack, LLC.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import httplib2
import logging
import re
import webob.exc
import wsgi


LOG = logging.getLogger("reddwarf.common.auth")


class AuthorizationMiddleware(wsgi.Middleware):

    def __init__(self, application, auth_providers, **local_config):
        self.auth_providers = auth_providers
        LOG.debug("Auth middleware providers: %s" % auth_providers)
        super(AuthorizationMiddleware, self).__init__(application,
            **local_config)

    def process_request(self, request):
        roles = request.headers.get('X_ROLE', '').split(',')
        LOG.debug("Processing auth request with roles: %s" % roles)
        tenant_id = request.headers.get('X-Tenant-Id', None)
        LOG.debug("Processing auth request with tenant_id: %s" % tenant_id)
        for provider in self.auth_providers:
            provider.authorize(request, tenant_id, roles)

    @classmethod
    def factory(cls, global_config, **local_config):
        def _factory(app):
            return cls(app, [TenantBasedAuth(), ServiceBasedAuth()],
                **local_config)
        return _factory


class ServiceBasedAuth(object):
    
    # Determine whether a user is allowed to access the DBaaS service
    # based on whether the mysql-admin role is enabled.
    def authorize(self, request, tenant_id, roles):
        
        if 'mysql-admin' in [role.lower() for role in roles] or 'mysql-user' in [role.lower() for role in roles]:
            LOG.debug("Authorized MySQL service: %s" % request)
            return True
        raise webob.exc.HTTPForbidden(_("This service is not available for this account."))


class TenantBasedAuth(object):

    # The paths differ from melange, so the regex must differ as well
    # reddwarf starts with a tenant_id
    tenant_scoped_url = re.compile("/(?P<tenant_id>.*?)/.*")

    def authorize(self, request, tenant_id, roles):
        LOG.debug("REQUEST PATH INFO: %s" % request.path_info)
        if ('mysql-admin' in [role.lower() for role in roles]) and request.path_info == "/":
            LOG.debug("Authorized admin request: %s" % request)
            return True
        if ('mysql-user' in [role.lower() for role in roles]) and request.path_info == "/":
            LOG.debug("Authorized mysql-user request for version API")
            return True 
        match_for_tenant = self.tenant_scoped_url.match(request.path_info)
        if (match_for_tenant and
            tenant_id == match_for_tenant.group('tenant_id')):
            LOG.debug("Authorized tenant '%(tenant_id)s' request: "
                      "%(request)s" % locals())
            return True
        raise webob.exc.HTTPForbidden(_("User with tenant id %s cannot "
                                        "access this resource") % tenant_id)
