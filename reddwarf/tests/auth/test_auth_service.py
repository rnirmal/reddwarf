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

import json
import mox
import stubout
import webob

from nova import test
from nova import flags
from nova import context

from reddwarf.api import flavors
from reddwarf.auth import auth_token
from reddwarf.auth import nova_auth_token
from reddwarf.tests import util

flavors_url = "%s/flavors" % util.v1_prefix

FLAGS = flags.FLAGS

data = json.dumps({'token': {'userId': 'admin'}})
TOKEN = "6df9c830-d3b0-41e7-bb56-3c568ae71f48"
unauth_response = {"unauthorized":
                    {"message": "The server could not verify that you are authorized to access the requested resource",
                     "code": 401}
                  }


def get_admin_auth_token(self, username, password):
    return "aat"


def validate_token(self, claims, tenant=None):
    if claims == TOKEN:
        return data, 200
    else:
        return data, 401


class AuthApiTest(test.TestCase):
    """Test various configuration update scenarios"""

    def setUp(self):
        super(AuthApiTest, self).setUp()
        self.context = context.get_admin_context()
        self.controller = flavors.ControllerV10()
        self.stubs.Set(auth_token.AuthProtocol, "get_admin_auth_token",
                       get_admin_auth_token)
        self.stubs.Set(auth_token.AuthProtocol, "_validate_token",
                       validate_token)
        app = nova_auth_token.KeystoneAuthShim(None)
        self.auth = auth_token.AuthProtocol(app, {})

    def tearDown(self):
        self.stubs.UnsetAll()
        super(AuthApiTest, self).tearDown()

    def _assert_401(self, res):
        self.assertDictMatch(json.loads(res.body), unauth_response)
        self.assertEqual(res.status_int, 401)

    def test_valid_token(self):
        req = webob.Request.blank(flavors_url)
        req.headers = [("X_AUTH_PROJECT_ID", "dbaas"),
                       ("X-AUTH-TOKEN", TOKEN)]
        res = req.get_response(util.wsgi_app(fake_auth=False))
        self.assertEqual(res.status_int, 200)

    def test_invalid_token(self):
        req = webob.Request.blank(flavors_url)
        req.headers = [("X_AUTH_PROJECT_ID", "dbaas"),
                       ("X-AUTH-TOKEN", "aat-asd")]
        res = req.get_response(util.wsgi_app(fake_auth=False))
        self._assert_401(res)

    def test_no_claims_provided(self):
        req = webob.Request.blank(flavors_url)
        req.headers = [("X_AUTH_PROJECT_ID", "dbaas")]
        res = req.get_response(util.wsgi_app(fake_auth=False))
        self._assert_401(res)

    def test_no_auth_project_id(self):
        req = webob.Request.blank(flavors_url)
        req.headers = [("X-AUTH-TOKEN", TOKEN)]
        res = req.get_response(util.wsgi_app(fake_auth=False))
        self._assert_401(res)

    def test_auth_project_id_path_no_match(self):
        req = webob.Request.blank(flavors_url)
        req.headers = [("X_AUTH_PROJECT_ID", "other"),
                       ("X-AUTH-TOKEN", TOKEN)]
        res = req.get_response(util.wsgi_app(fake_auth=False))
        self._assert_401(res)

    def test_validate_status(self):
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

    def test_cache_hit(self):
        cache_key = "aat/dbaas"
        self.auth.cache.set_value(cache_key, (data, 200))
        req = webob.Request.blank(flavors_url)
        req.headers = [("X_AUTH_PROJECT_ID", "dbaas"),
                       ("X-AUTH-TOKEN", "aat")]
        res = req.get_response(util.wsgi_app(fake_auth=False))
        self.assertEqual(res.status_int, 200)
