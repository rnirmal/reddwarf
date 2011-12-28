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
Tests for Users API calls
"""

import json
import mox
import stubout
import webob
from paste import urlmap
from nose.tools import raises

from nova import context
from nova import test
from nova.compute import power_state

import reddwarf
from reddwarf import exception
from reddwarf.api import users
from reddwarf.tests import util

databases_url = "%s/1/users" % util.v1_instances_prefix


class FakeState(object):
    def __init__(self):
        self.state = power_state.RUNNING

def guest_status_get(id):
    return FakeState()

def localid_from_uuid(id):
    return id

def instance_exists(ctxt, instance_id, compute_api):
    return True

def request_obj(url, method, body=None):
    req = webob.Request.blank(url)
    req.method = method
    if body:
        req.body = json.dumps(body)
    req.headers["content-type"] = "application/json"
    return req

class UserApiTest(test.TestCase):
    """Test various Database API calls"""

    def setUp(self):
        super(UserApiTest, self).setUp()
        self.context = context.get_admin_context()
        self.controller = users.Controller()
        self.stubs.Set(reddwarf.api.common, "instance_exists", instance_exists)
        self.stubs.Set(reddwarf.db.api, "localid_from_uuid", localid_from_uuid)
        self.stubs.Set(reddwarf.db.api, "guest_status_get", guest_status_get)

    def tearDown(self):
        self.stubs.UnsetAll()
        super(UserApiTest, self).tearDown()

    def test_delete_user_name_begin_space(self):
        req = request_obj(databases_url+"/%20test", 'DELETE')
        res = req.get_response(util.wsgi_app(fake_auth_context=self.context))
        self.assertEqual(res.status_int, 400)

    def test_delete_user_name_end_space(self):
        req = request_obj(databases_url+"/test%20", 'DELETE')
        res = req.get_response(util.wsgi_app(fake_auth_context=self.context))
        self.assertEqual(res.status_int, 400)

    def test_create_user_name_begin_space(self):
        body = {'users': [{'name': ' test', 'password': 'password'}]}
        req = request_obj(databases_url, 'POST', body=body)
        res = req.get_response(util.wsgi_app(fake_auth_context=self.context))
        self.assertEqual(res.status_int, 400)

    def test_create_user_name_end_space(self):
        body = {'users': [{'name': 'test ', 'password': 'password'}]}
        req = request_obj(databases_url, 'POST', body=body)
        res = req.get_response(util.wsgi_app(fake_auth_context=self.context))
        self.assertEqual(res.status_int, 400)

    @raises(exception.BadRequest)
    def test_create_user_no_password(self):
        body = {'users': [{'name': 'test'}]}
        self.controller._validate(body)

    @raises(exception.BadRequest)
    def test_create_user_no_name(self):
        body = {'users': [{'password': 'password'}]}
        self.controller._validate(body)

    @raises(exception.BadRequest)
    def test_create_user_no_name_or_password(self):
        body = {'users': [{'name1': 'test'}]}
        self.controller._validate(body)

    @raises(exception.BadRequest)
    def test_create_user_no_name_or_password(self):
        self.controller._validate("")

    def test_create_user_no_name_or_password(self):
        body = {'users': [{'name': 'test', 'password': 'password'}]}
        self.controller._validate(body)
