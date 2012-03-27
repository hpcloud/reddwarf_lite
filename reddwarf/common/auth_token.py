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
import webob.exc
import json
import time


LOG = logging.getLogger("reddwarf.common.auth_token")

class InvalidUserToken(Exception):
    pass

class ServiceError(Exception):
    pass

class NotFoundError(Exception):
    pass

class UnauthorizedError(Exception):
    pass

class ServerError(Exception):
    pass
    
class TokenBasedAuth(object):
    
    def __init__(self, app, conf):
        LOG.info('Starting Token Based Authentication Middleware')
        self.conf = conf
        self.app = app
        
        self.auth_host = conf.get('auth_host', 'region-a.geo-1.identity.hpcloudsvc.com')
        self.auth_port = int(conf.get('auth_port', 35357))
        self.auth_protocol = conf.get('auth_protocol', 'https')
        self.auth_version = conf.get('auth_version', 'v2.0')
        self.retry_limit = int(conf.get('retry_limit', 1))
        self.retry_count = 0
        self.retry_sleep_seconds = int(conf.get('retry_sleep_seconds', 1))
        
        if self.auth_protocol == 'http':
            self.http_client_class = httplib2.HTTPConnectionWithTimeout
        else:
            self.http_client_class = httplib2.HTTPSConnectionWithTimeout
            

    def __call__(self, env, start_response):
        """Handle incoming request.

        Authenticate send downstream on success. Reject request if
        we can't authenticate.
        """
        
        self.user_token = ""
        self.user_id = ""
        self.user_username = ""
        self.user_tenant_id = ""
        self.user_tenant_username = ""
        self.user_roles = ""
        
        LOG.debug("Started Token Based Authentication")
        try:
            self._authorize(env)
            
            user_headers = {
                'X-Identity-Status': 'Confirmed',
                'X-Tenant-Id': self.user_tenant_id,
                'X-Tenant-Name': self.user_tenant_username,
                'X-User-Id': self.user_id,
                'X-User-Name': self.user_username,
                'X-Roles': self.user_roles,
                # Deprecated
                'X-User': self.user_username,
                'X-Tenant': self.user_tenant_username,
                'X-Role': self.user_roles
            }
            
            self._add_headers(env, user_headers)
            
            return self.app(env, start_response)

        except InvalidUserToken, (logMessage, publicMessage):
            LOG.error('401 Error returned - %s' % logMessage)
            resp = webob.exc.HTTPUnauthorized(explanation=publicMessage)
            return resp(env, start_response)

        except ServiceError, (logMessage, publicMessage):
            LOG.error('503 error returned : %s' % logMessage)
            resp = webob.exc.HTTPServiceUnavailable(explanation=publicMessage)
            return resp(env, start_response)
        
        except NotFoundError, (logMessage, publicMessage):
            LOG.error('404 error returned : %s' % logMessage)
            resp = webob.exc.HTTPNotFound(explanation=publicMessage)
            return resp(env, start_response)
        
        except UnauthorizedError, (logMessage, publicMessage):
            LOG.error('401 error returned : %s' % logMessage)
            resp = webob.exc.HTTPUnauthorized(explanation=publicMessage)
            return resp(env, start_response)
        
        except ServerError, (logMessage, publicMessage):
            LOG.error('500 error returned : %s' % logMessage)
            resp = webob.exc.HTTPServerError(explanation=publicMessage)
            return resp(env, start_response)


    def _authorize(self, environment):

        """Get the user token from the header"""
        self.user_token = self._get_header(environment, 'X-Auth-Token')
        self.user_tenant_username = self._get_header(environment, 'X-Auth-Project-Id')
        
        """Check to see if our required headers are passed in"""
        if self.user_token is None:
            msg = ("X-Auth-Token not supplied in request header.  ie : 'X-Auth-Token: [authentication token]'")
            LOG.warn(msg % locals())
            raise InvalidUserToken(msg, msg)

        if self.user_tenant_username is None:
            msg = ("X-Auth-Project-Id not supplied in request header.  ie : 'X-Auth-Project-Id: [authentication tenant name]'")
            LOG.warn(msg % locals())
            raise InvalidUserToken(msg, msg)
        
        
        """Setup our json body to post"""
        params = {
            'auth': {
                'tenantName': self.user_tenant_username,
                'token': {
                    'id': self.user_token
                }
            }
        }
        
        """Post our body to the server using JSON"""
        response, data = self._json_request('POST',
                                            '/%s/tokens' % self.auth_version,
                                            body=params)

        if response.status == 200:
            remote_address = getattr(environment, 'REMOTE_ADDR', '127.0.0.1')
            
            """Get the user and token information from response"""
            try :
                user = data['access']['user']
                token = data['access']['token']
                self.user_id = user.get('id')
                self.user_username = user.get('name')
                self.user_tenant_id = token['tenant']['id']
                self.user_tenant_username = token['tenant']['name']
                self.user_roles = ','.join([role['name'] for role in user.get('roles', [])])
            except : 
                logMsg = ("Could not extract user_id and username from response data \n Response Data \n %s" % data)
                pubMsg = ("There was an error processing your request.  Please try again later.")
                raise ServerError(logMsg, pubMsg)
            
            LOG.info("200 Authorized - Returned to client")
            return True
        if response.status == 404:
            raise NotFoundError("Call not found?", None)
        if response.status == 401:
            raise UnauthorizedError("User was not authenticated", None)
        else:
            LOG.error('Bad response code while validating token: %s' %
                         response.status)

        """Retry authentication here"""
        if not (self.retry_count == self.retry_limit):
            LOG.info('Retrying validation - Sleeping for %s seconds' % self.retry_sleep_seconds)
            self.retry_count += 1
            time.sleep(self.retry_sleep_seconds)
            return self._authorize(environment)
        else:
            raise UnauthorizedError("Retry limit exceeded for token authorization", None)
        
    def _get_http_connection(self):
        return self.http_client_class(self.auth_host, self.auth_port)
    
    def _header_to_env_var(self, key):
        """Convert header to wsgi env variable.

        :param key: http header name (ex. 'X-Auth-Token')
        :return wsgi env variable name (ex. 'HTTP_X_AUTH_TOKEN')

        """
        return  'HTTP_%s' % key.replace('-', '_').upper()
    
    def _get_header(self, env, key, default=None):
        """Get http header from environment."""
        env_key = self._header_to_env_var(key)
        return env.get(env_key, default)
    
    def _add_headers(self, env, headers):
        """Add http headers to environment."""
        for (k, v) in headers.iteritems():
            env_key = self._header_to_env_var(k)
            env[env_key] = v

    def _json_request(self, method, path, body=None, additional_headers=None):
        """HTTP request helper used to make json requests.

        :param method: http method
        :param path: relative request url
        :param body: dict to encode to json as request body. Optional.
        :param additional_headers: dict of additional headers to send with
                                   http request. Optional.
        :return (http response object, response body parsed as json)

        """
        conn = self._get_http_connection()

        kwargs = {
            'headers': {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            },
        }

        if additional_headers:
            kwargs['headers'].update(additional_headers)

        if body:
            kwargs['body'] = json.dumps(body)

        try:
            conn.request(method, path, **kwargs)
            response = conn.getresponse()
            body = response.read()
        except Exception, e:
            logMsg = "HTTP Connection Exception : %s" % e
            raise ServiceError(logMsg, None)
        finally:
            conn.close()

        try:
            data = json.loads(body)
        except ValueError:
            data = {}
            raise ServerError("Keystone did not return json-encoded body", None)

        return response, data
    
    
def filter_factory(global_conf, **local_conf):
    """Returns a WSGI filter app for use with paste.deploy."""
    LOG.debug("Created Auth-Token Middleware: %s" % local_conf)
    conf = global_conf.copy()
    conf.update(local_conf)

    def auth_filter(app):
        return TokenBasedAuth(app, conf)
    
    return auth_filter


def app_factory(global_conf, **local_conf):
    conf = global_conf.copy()
    conf.update(local_conf)
    return TokenBasedAuth(None, conf)