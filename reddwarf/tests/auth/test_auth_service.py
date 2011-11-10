#    Copyright 2011 OpenStack LLC
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
Tests the Authorization Service
"""

import mox
import unittest

from beaker.cache import CacheManager
from nova import test
from nova import flags
import reddwarf.auth.auth_token as auth
import reddwarf.auth.nova_auth_token
from webob.exc import HTTPUnauthorized

FLAGS = flags.FLAGS
CONF = {
    "__file__": "/home/vagrant/reddwarf-api-paste.ini",
    "auth_host": "127.0.0.1",
    "auth_port": "5001",
    "auth_protocol": "http",
    "auth_version": "v1.1",
    "cache-type": "memory",
    "here": "/home/vagrant",
    "service_host": "127.0.0.1",
    "service_pass": "serviceadmin",
    "service_port": "5000",
    "service_protocol": "http",
    "service_user": "service-admin",
    "verbose": "1"
}
ENV = {
    "CONTENT_TYPE": "text/plain",
    "GATEWAY_INTERFACE": "CGI/1.1",
    "HTTP_ACCEPT_ENCODING": "gzip, deflate",
    "HTTP_HOST": "localhost:8775",
    "HTTP_USER_AGENT": "python-novaclient",
    "HTTP_X_AUTH_PROJECT_ID": "admin",
    "HTTP_X_AUTH_TOKEN": "6df9c830-d3b0-41e7-bb56-3c568ae71f48",
    "PATH_INFO": "/dbaas/flavors/detail",
    "QUERY_STRING": "fresh=1321634468.05",
    "REMOTE_ADDR": "127.0.0.1",
    "REQUEST_METHOD": "GET",
    "SCRIPT_NAME": "/v1.0",
    "SERVER_NAME": "127.0.0.1",
    "SERVER_PORT": "8775",
    "SERVER_PROTOCOL": "HTTP/1.0",
    "wsgi.url_scheme": "http"
}

class AuthApiTest(test.TestCase):
    """Test various configuration update scenarios"""

    def setUp(self):
        super(AuthApiTest, self).setUp()
#        self.mox = mox.Mox()
        app = reddwarf.auth.nova_auth_token.KeystoneAuthShim(None)

        self.auth = auth.AuthProtocol(app, CONF)

        # Create cache manager
        self.cache_type = CONF.get('cache_type', 'memory')
        cm = CacheManager(type=self.cache_type)
        self.cache = cm.get_cache('dbaas')
        
    def test_1_make_auth_call(self):
        start_response = {}

        self.mox.StubOutWithMock(self.auth, '__call__')
        self.auth.__call__(ENV, start_response).AndReturn(None)
        self.mox.ReplayAll()

        self.assertEqual(self.auth.__call__(ENV, start_response), None)

    def test_2_get_claims(self):
        claim = self.auth._get_claims(ENV)
        self.assertEqual(claim, ENV.get('HTTP_X_AUTH_TOKEN'))

    def test_3_get_admin_auth_token_valid(self):
        service_user = ENV.get('service_user')
        service_pass = ENV.get('service_pass')
        admin_token = 'admintoken'

        self.mox.StubOutWithMock(self.auth, 'get_admin_auth_token')
        self.auth.get_admin_auth_token(service_user, service_pass).AndReturn(admin_token)
        self.mox.ReplayAll()

        token = self.auth.get_admin_auth_token(service_user, service_pass)
        self.assertEqual(admin_token, token)

    def test_4_get_admin_auth_token_fail(self):
        service_user = 'service_user'
        service_pass = 'service_pass'
        self.assertRaises(HTTPUnauthorized, self.auth.get_admin_auth_token, service_user, service_pass)

    def test_5_reject_request(self):
        self.mox.StubOutWithMock(self.auth, '_reject_request')
        self.auth._reject_request(ENV, {}).AndReturn(HTTPUnauthorized)
        self.mox.ReplayAll()
        self.assertEqual(HTTPUnauthorized, self.auth._reject_request(ENV, {}))

    def test_6_reject_claims(self):
        self.mox.StubOutWithMock(self.auth, '_reject_claims')
        self.auth._reject_claims(ENV, {}).AndReturn(HTTPUnauthorized)
        self.mox.ReplayAll()
        result = self.auth._reject_claims(ENV, {})
        self.assertEqual(HTTPUnauthorized, result)

    def test_7_validate_token(self):
        claim = self.auth._get_claims(ENV)
        data, status = self.auth._validate_token(claim)

    def test_8_validate_status(self):
        status = 200
        self.assertTrue(self.auth._validate_status(status))
        status = 202
        self.assertTrue(self.auth._validate_status(status))
        status = 404
        self.assertFalse(self.auth._validate_status(status))
        status = 500
        self.assertFalse(self.auth._validate_status(status))
        status = 503
        self.assertFalse(self.auth._validate_status(status))

