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

"""
TOKEN-BASED AUTH MIDDLEWARE

This WSGI component performs multiple jobs:
- it verifies that incoming client requests have valid tokens by verifying
    tokens with the auth service.
- it will reject unauthenticated requests
- it will collect and forward identity information from a valid token
    such as user name etc...

Refer to: http://wiki.openstack.org/openstack-authn


HEADERS
-------
Headers starting with HTTP_ is a standard http header
Headers starting with HTTP_X is an extended http header

> Coming in from initial call from client or customer
HTTP_X_AUTH_TOKEN   : the client token being passed in
> Used for communication between components
www-authenticate    : only used if this component is being used remotely
HTTP_AUTHORIZATION  : basic auth password used to validate the connection

> What we add to the request for use by the OpenStack service
HTTP_X_AUTHORIZATION: the client identity being passed in

"""

import base64
import json

from beaker.cache import CacheManager
from datetime import datetime
from eventlet import wsgi
from eventlet.green import httplib
from paste.deploy import loadapp

from nova import log as logging
from nova import flags
from nova.api.openstack import faults

from reddwarf import exception

FLAGS = flags.FLAGS
flags.DEFINE_integer('reddwarf_auth_cache_expire_time', 60*5,
                     'Time in seconds for the cache to expire user tokens')

LOG = logging.getLogger(__name__)

PROTOCOL_NAME = "Token Authentication"

class AuthProtocol(object):
    """Auth Middleware that handles authenticating client calls"""

    def __init__(self, app, conf):
        """ Common initialization code """
        print "Starting the %s component" % PROTOCOL_NAME

        self.conf = conf
        self.app = app

        # where to find the auth service (we use this to validate tokens)
        self.auth_host = conf.get('auth_host')
        self.auth_port = int(conf.get('auth_port', 443))
        self.auth_protocol = conf.get('auth_protocol', 'https')
        self.auth_type = conf.get('auth_type', '')
        self.auth_version = conf.get('auth_version', 'v1.1')
        self.service_host = conf.get('service_host')
        self.service_port = conf.get('service_port')

        # where to tell clients to find the auth service (default to url
        # constructed based on endpoint we have for the service to use)
        self.auth_location = conf.get('auth_uri', "%s://%s:%s/%s"
                                      % (self.auth_protocol, self.service_host,
                                         self.service_port, self.auth_version))

        # Assign the functions w.r.to to the auth api version
        if self.auth_version == 'v1.1':
            self.validate_token_path = "/v1.1/token"
            self.service_auth_path = "/v1.1/auth"
            self._expound_claims = self._expound_claims_1_1
        else:
            self.validate_token_path = "/v2.0/tokens"
            self.service_auth_path = "/v2.0/tokens"
            self._expound_claims = self._expound_claims_2_0

        # Credentials used to verify this component with the Auth service since
        # validating tokens is a privileged call
        service_user = conf.get('service_user')
        service_pass = conf.get('service_pass')
        self.admin_token = self.get_admin_auth_token(service_user,
                                                     service_pass)
        self.basic_auth = base64.b64encode("%(service_user)s:%(service_pass)s"
                                           % locals())

        # Create cache manager
        self.cache_type = conf.get('cache_type', 'memory')
        cm = CacheManager(type=self.cache_type)
        self.cache = cm.get_cache('dbaas')

    def __call__(self, env, start_response):
        """ Handle incoming request. Authenticate. And send downstream. """
        proxy_headers = self._prep_headers(env)

        # Retrieve the tenant, if not reject the request
        tenant = self._retrieve_tenant(env)
        if not tenant:
            return self._reject_request(env, start_response)

        # Look for authentication claims
        claims = self._get_claims(env)
        if not claims:
            # No claim(s) provided
            return self._reject_request(env, start_response)

        #set the caching key to the concatenation of claim and tenant
        cache_key = "%s/%s" % (claims,tenant)

        # this request is presenting claims. Let's validate them
        #TODO(cp16net) what happens with 1000s of users being cached?
        if self.cache.has_key(cache_key):
            # get the cached values
            data, status = self.cache.get_value(cache_key)
            valid = self._validate_status(status)

            if not valid:
                # Keystone rejected claim
                return self._reject_claims(env, start_response)
        else:
            # need to get the values and then cache them if valid
            try:
                data, status = self._validate_token(claims, tenant)
            except :
                msg = ("Authorization Service is not available at this "
                       "time for (tenant=%s)." % tenant)
                LOG.error(msg)
                return faults.Fault(exception.ServiceUnavailable(msg)) \
                                    (env, start_response)

            valid = self._validate_status(status)
            if not valid:
                # rejected claim because claims are not valid
                return self._reject_claims(env, start_response)
            else:
                # claim is valid so cache the result from validation
                cache_key = "%s/%s" % (claims,tenant)
                self.cache.set_value(cache_key, (data, status),
                                     expiretime=FLAGS.reddwarf_auth_cache_expire_time)

        self._decorate_request("X_IDENTITY_STATUS", "Confirmed", env,
                               proxy_headers)

        # Collect information about valid claims
        if valid:
            # This is only required for auth 1.1, 2.0 onwards this is retrieved
            # from the validation step.
            self._decorate_request('X_TENANT', tenant, env, proxy_headers)
            env = self._expound_claims(data, env, proxy_headers)

        return self.app(env, start_response)

    def _retrieve_tenant(self, env):
        # Retrieve the tenant/accountid from the url
        path_info = env.get('PATH_INFO', '/')
        if path_info not in ["", "/"]:
            return path_info.split("/")[1]
        else:
            return None

    def _prep_headers(self, env):
        # Prep headers to forward request to local or remote downstream service
        proxy_headers = env.copy()
        for header in proxy_headers.keys():
            if header[0:5] == 'HTTP_':
                proxy_headers[header[5:]] = proxy_headers[header]
                del proxy_headers[header]
        return proxy_headers

    def _get_claims(self, env):
        """Get claims from request"""
        claims = env.get('HTTP_X_AUTH_TOKEN', env.get('HTTP_X_STORAGE_TOKEN'))
        return claims

    def get_admin_auth_token(self, username, password):
        """
        This function gets an admin auth token to be used by this service to
        validate a user's token. Validate_token is a privileged call so
        it needs to be authenticated by a service that is calling it
        """
        headers = {'Content-type': 'application/json',
                   'Accept': 'application/json'}
        request_body = {'passwordCredentials': {'username': username,
                                                'password': password}}
        conn = get_connection(self.auth_protocol, self.auth_host,
                              self.auth_port)
        conn.request("POST", self.service_auth_path, json.dumps(request_body),
                     headers=headers)
        response = conn.getresponse()
        data = response.read()
        try:
            if not data or not self._validate_status(response.status):
                if response.status == 302:
                    # Can be ignored because the service relies on basic auth
                    return ""
                msg = "Error authenticating service with user(%s)" % username
                LOG.error(msg)
                raise exception.Unauthorized(msg)
            else:
                body = json.loads(data)
                admin_token = body['auth']['token']['id']
                return admin_token
        except:
            msg = "Error authenticating service with user(%s)" % username
            LOG.error(msg)
            raise exception.Unauthorized(msg)

    def _reject_request(self, env, start_response):
        """Redirect client to auth server"""
        tenant = self._retrieve_tenant(env)
        LOG.error("Rejecting the authentication request "
                  "for (tenant=%s)" % tenant)
        return faults.Fault(exception.Unauthorized())(env, start_response)

    def _reject_claims(self, env, start_response):
        """Client sent bad claims"""
        tenant = self._retrieve_tenant(env)
        LOG.error("Rejecting the claim for (tenant=%s)" % tenant)
        return faults.Fault(exception.Unauthorized())(env, start_response)

    def _validate_token(self, claims, tenant=None):
        """Make the call to Keystone and get the return code and data"""
        headers = {'Content-type': 'application/json',
                   'Accept': 'application/json',
                   'X-Auth-Token': self.admin_token,
                   'Authorization': 'Basic %s' % self.basic_auth}

        conn = get_connection(self.auth_protocol, self.auth_host,
                              self.auth_port)
        conn.request("GET", "%s/%s?belongsTo=%s&type=%s" %
                     (self.validate_token_path, claims, tenant, self.auth_type),
                     headers=headers)
        response = conn.getresponse()
        data = response.read()
        conn.close()
        return data, response.status

    def _validate_status(self, status):
        """Check status is in list of OK http statuses"""
        return status in (200, 202)

    def _expound_claims_1_1(self, data, env, proxy_headers):
        # Valid token. Get user data and put it in to the call
        # so the downstream service can use it
        token_info = json.loads(data)
        userId = token_info['token']['userId']

        # Store authentication data
        self._decorate_request('X_AUTHORIZATION', "Proxy %s" % userId, env,
                               proxy_headers)
        self._decorate_request('X_USER', userId, env, proxy_headers)
        return env

    def _expound_claims_2_0(self, data, env, proxy_headers):
        # Valid token. Get user data and put it in to the call
        # so the downstream service can use it
        token_info = json.loads(data)
        roles = []
        role_refs = token_info['auth']['user']['roleRefs']
        if role_refs is not None:
            for role_ref in role_refs:
                roles.append(role_ref['roleId'])

        try:
            tenant = token_info['auth']['token']['tenantId']
        except:
            tenant = None
        if not tenant:
            tenant = token_info['auth']['user']['tenantId']
        verified_claims = {'user': token_info['auth']['user']['username'],
                    'tenant': tenant,
                    'roles': roles}

        # Store authentication data
        if verified_claims:
            self._decorate_request('X_AUTHORIZATION', "Proxy %s" %
                                   verified_claims['user'], env, proxy_headers)
            self._decorate_request('X_TENANT', verified_claims['tenant'], env,
                                   proxy_headers)
            self._decorate_request('X_USER', verified_claims['user'], env,
                                   proxy_headers)
            if 'roles' in verified_claims and len(verified_claims['roles']) > 0:
                if verified_claims['roles'] is not None:
                    roles = ','.join([role for role in verified_claims['roles']])
                    self._decorate_request('X_ROLE', str(roles), env,
                                           proxy_headers)
        return env

    def _decorate_request(self, index, value, env, proxy_headers):
        """Add headers to request"""
        proxy_headers[index] = value
        env["HTTP_%s" % index] = value


def filter_factory(global_conf, **local_conf):
    """Returns a WSGI filter app for use with paste.deploy."""
    conf = global_conf.copy()
    conf.update(local_conf)

    def auth_filter(app):
        return AuthProtocol(app, conf)
    return auth_filter


def app_factory(global_conf, **local_conf):
    conf = global_conf.copy()
    conf.update(local_conf)
    return AuthProtocol(None, conf)


def get_connection(type, host, port):
    if type == "https":
        return httplib.HTTPSConnection("%(host)s:%(port)s" % locals())
    else:
        return httplib.HTTPConnection("%(host)s:%(port)s" % locals())
