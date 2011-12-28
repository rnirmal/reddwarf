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
Tests for Databases API calls
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
from reddwarf.api import databases
from reddwarf.tests import util

databases_url = "%s/1/databases" % util.v1_instances_prefix

class FakeState(object):
    def __init__(self):
        self.state = power_state.RUNNING

def guest_status_get(id):
    return FakeState()

def localid_from_uuid(id):
    return id

def list_databases_exception(self, req, instance_id):
    raise Exception()

def instance_exists(ctxt, instance_id, compute_api):
    return True

def request_obj(url, method, body=None):
    req = webob.Request.blank(url)
    req.method = method
    if body:
        req.body = json.dumps(body)
    req.headers["content-type"] = "application/json"
    return req

class DatabaseApiTest(test.TestCase):
    """Test various Database API calls"""

    def setUp(self):
        super(DatabaseApiTest, self).setUp()
        self.context = context.get_admin_context()
        self.controller = databases.Controller()
        self.stubs.Set(reddwarf.api.common, "instance_exists", instance_exists)
        self.stubs.Set(reddwarf.db.api, "localid_from_uuid", localid_from_uuid)
        self.stubs.Set(reddwarf.db.api, "guest_status_get", guest_status_get)

    def tearDown(self):
        self.stubs.UnsetAll()
        super(DatabaseApiTest, self).tearDown()

    def test_list_databases(self):
        self.stubs.Set(reddwarf.guest.api.API, "list_databases",
                       list_databases_exception)
        req = webob.Request.blank(databases_url)
        res = req.get_response(util.wsgi_app())
        self.assertEqual(res.status_int, 500)

    def test_show_database(self):
        req = webob.Request.blank('%s/testdb' % databases_url)
        res = req.get_response(util.wsgi_app())
        self.assertEqual(res.status_int, 501)

    @raises(exception.BadRequest)
    def test_validate_empty_body(self):
        self.controller._validate("")

    @raises(exception.BadRequest)
    def test_validate_no_databases_element(self):
        body = {'database': ''}
        self.controller._validate(body)

    @raises(exception.BadRequest)
    def test_validate_no_database_name(self):
        body = {'databases': [{'name1': 'testdb'}]}
        self.controller._validate(body)

    def test_valid_create_databases_body(self):
        body = {'databases': [{'name': 'testdb'}]}
        self.controller._validate(body)

    def test_delete_database_name_begin_space(self):
        req = request_obj(databases_url+"/%20test", 'DELETE')
        res = req.get_response(util.wsgi_app(fake_auth_context=self.context))
        self.assertEqual(res.status_int, 400)

    def test_delete_database_name_end_space(self):
        req = request_obj(databases_url+"/test%20", 'DELETE')
        res = req.get_response(util.wsgi_app(fake_auth_context=self.context))
        self.assertEqual(res.status_int, 400)

    def test_create_database_name_begin_space(self):
        body = {'databases': [{'name': ' test'}]}
        req = request_obj(databases_url, 'POST')
        res = req.get_response(util.wsgi_app(fake_auth_context=self.context))
        self.assertEqual(res.status_int, 400)

    def test_create_database_name_end_space(self):
        body = {'databases': [{'name': 'test '}]}
        req = request_obj(databases_url, 'POST')
        res = req.get_response(util.wsgi_app(fake_auth_context=self.context))
        self.assertEqual(res.status_int, 400)
