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
Tests for Instances API calls
"""

import mox
import json
import stubout
import webob
from paste import urlmap

import nova
from nova import context
from nova import test
from nova.compute import vm_states
from nova.compute import power_state
import nova.exception as nova_exception


import reddwarf
from reddwarf.api import instances
from reddwarf.db import models
from reddwarf.tests import util

instances_url = util.v1_instances_prefix

def localid_from_uuid(id):
    return id

def compute_get(ctxt, id):
    return {'vm_state': vm_states.ACTIVE,
            'id': 1,}

def compute_get_exception(ctxt, id):
    raise nova_exception.NotFound()

def compute_get_building(ctxt, id):
    return {'vm_state': vm_states.BUILDING,
            'id': 1,
            }
def guest_status_get_running(id, session=None):
    status = models.GuestStatus()
    status.state = power_state.RUNNING
    return status

def guest_status_get_failed(id, session=None):
    status = models.GuestStatus()
    status.state = power_state.FAILED
    return status

def request_obj(url, method, body):
    req = webob.Request.blank(url)
    req.method = method
    req.body = json.dumps(body)
    req.headers["content-type"] = "application/json"
    return req

class InstanceApiTest(test.TestCase):
    """Test various Database API calls"""

    def setUp(self):
        super(InstanceApiTest, self).setUp()
        self.context = context.get_admin_context()
        self.controller = instances.Controller()
        self.stubs.Set(reddwarf.db.api, "localid_from_uuid", localid_from_uuid)
        self.stubs.Set(nova.compute.API, "get", compute_get)

    def tearDown(self):
        self.stubs.UnsetAll()
        super(InstanceApiTest, self).tearDown()

    def test_instances_delete(self):
        self.stubs.Set(nova.compute.API, "get", compute_get_exception)
        body = {}
        req = request_obj('%s/1' % instances_url, 'DELETE', body)
        res = req.get_response(util.wsgi_app(fake_auth_context=self.context))
        self.assertEqual(res.status_int, 404)

    def test_instances_delete(self):
        self.stubs.Set(nova.compute.API, "get", compute_get_building)
        self.stubs.Set(reddwarf.db.api, "guest_status_get", guest_status_get_running)
        body = {}
        req = request_obj('%s/1' % instances_url, 'DELETE', body)
        res = req.get_response(util.wsgi_app(fake_auth_context=self.context))
        self.assertEqual(res.status_int, 422)

    def test_instances_delete_failed(self):
        self.stubs.Set(nova.compute.API, "get", compute_get_building)
        self.stubs.Set(reddwarf.db.api, "guest_status_get", guest_status_get_failed)
        body = {}
        req = request_obj('%s/1' % instances_url, 'DELETE', body)
        res = req.get_response(util.wsgi_app(fake_auth_context=self.context))
        self.assertEqual(res.status_int, 202)
