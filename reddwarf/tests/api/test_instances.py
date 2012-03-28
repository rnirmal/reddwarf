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
from reddwarf import exception
from reddwarf.api import instances
from reddwarf.db import models
from reddwarf.tests import util

from nose.tools import raises

instances_url = util.v1_instances_prefix

def localid_from_uuid(id):
    return id

def compute_delete(self, ctxt, id):
    return

def compute_get(self, ctxt, id):
    return {'vm_state': vm_states.ACTIVE,
            'id': 1,}

def compute_get_exception(self, ctxt, id):
    raise nova_exception.NotFound()

def compute_get_building(self, ctxt, id):
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

def guest_status_delete(id, session=None):
    return

def request_obj(url, method, body={}):
    req = webob.Request.blank(url)
    req.method = method
    if method in ['POST', 'PUT']:
        req.body = json.dumps(body)
    req.headers["content-type"] = "application/json"
    return req

def server_show(self, req, instance_id):
    server = {'uuid': '123', 'id': 1, 'name': 'test', 'status': 'ACTIVE',
              'volume': {'size': 1}}
    return {'server': server}

def guest_status(local_ids):

    class StatusDict(object):
        def __init__(self, id, state):
            self.id = id
            self.instance_id = id
            self.state = state

    class Result(object):
        def __init__(self, items):
            self.items = items

        def all(self):
            return self.items

    status = []
    for id in local_ids:
        d1 = StatusDict(id, 1)
        status.append(d1)
    return Result(status)

def get_guest_info(self, context, server):
    return [], []

def get_volume_info(self, context, id):
    raise exception.GuestError()

def build_view(self, server, req, instance):
    return {'uuid': '123', 'id': 1, 'name': 'test', 'status': 'ACTIVE',
            'volume': {'size': 1}}


class InstanceApiTest(test.TestCase):
    """Test various Database API calls"""

    def setUp(self):
        super(InstanceApiTest, self).setUp()
        self.context = context.get_admin_context()
        self.controller = instances.Controller()
        self.stubs.Set(reddwarf.db.api, "localid_from_uuid", localid_from_uuid)
        self.stubs.Set(nova.compute.API, "get", compute_get)
        self.stubs.Set(reddwarf.db.api, "guest_status_get", guest_status_get_running)

    def tearDown(self):
        self.stubs.UnsetAll()
        super(InstanceApiTest, self).tearDown()

    def test_instances_delete_not_found(self):
        self.stubs.Set(nova.compute.API, "get", compute_get_exception)
        req = request_obj('%s/1' % instances_url, 'DELETE')
        res = req.get_response(util.wsgi_app(fake_auth_context=self.context))
        self.assertEqual(res.status_int, 404)

    def test_instances_delete_unprocessable(self):
        self.stubs.Set(nova.compute.API, "get", compute_get_building)
        req = request_obj('%s/1' % instances_url, 'DELETE')
        res = req.get_response(util.wsgi_app(fake_auth_context=self.context))
        self.assertEqual(res.status_int, 422)

    def test_instances_delete(self):
        self.stubs.Set(nova.compute.API, "delete", compute_delete)
        self.stubs.Set(nova.compute.API, "get", compute_get)
        self.stubs.Set(reddwarf.db.api, "guest_status_delete", guest_status_delete)
        req = request_obj('%s/1' % instances_url, 'DELETE')
        res = req.get_response(util.wsgi_app(fake_auth_context=self.context))
        self.assertEqual(res.status_int, 202)
        self.assertEqual(res.body, '')

    def test_instance_get_errored_guest(self):
        self.stubs.Set(nova.api.openstack.servers.ControllerV11, "show",
                       server_show)
        self.stubs.Set(reddwarf.db.api, 'guest_status_get_list', guest_status)
        self.stubs.Set(reddwarf.api.instances.Controller, '_get_guest_info',
                       get_guest_info)
        self.stubs.Set(reddwarf.guest.api.API, 'get_volume_info',
                       get_volume_info)
        self.stubs.Set(reddwarf.api.views.instances.ViewBuilder,
                       '_build_basic', build_view)
        self.stubs.Set(reddwarf.api.views.instances.ViewBuilder,
                       '_build_detail', build_view)
        req = request_obj('%s/1' % instances_url, 'GET')
        res = req.get_response(util.wsgi_app(fake_auth_context=self.context))
        self.assertEqual(res.status_int, 200)
        volume = json.loads(res.body)['instance']['volume']
        self.assertTrue(volume.get('size', None) is not None)
        self.assertTrue(volume.get('used', None) is None)


class InstanceApiValidation(test.TestCase):
    """
    Test the instance api validation methods

    Unit Test cases for resize instance/volume
    1. {resize: {volume: {size: 2}}} - pass
    2. {resize: {volume: {}}}        - fail
    3. {resize: {}}                  - fail
    4. {resize: {flavorRef: 2}}      - pass
    5. {resize: {flavorRef: 2,
                 volume: {size: 2}}} - fail
    """

    resize_body = {'resize': {'volume': {'size': 2}}}

    def setUp(self):
        super(InstanceApiValidation, self).setUp()
        self.context = context.get_admin_context()
        self.controller = instances.Controller()

    @raises(exception.BadRequest)
    def test_create_empty_body(self):
        self.controller._validate({})

    def test_valid_resize_volume_is_not_emtpty(self):
        self.controller._validate_empty_body(self.resize_body)

    def test_valid_single_resize_in_body(self):
        self.controller._validate_single_resize_in_body(self.resize_body)

    def test_valid_resize_volume(self):
        self.controller._validate_resize(self.resize_body, 1)

    @raises(exception.BadRequest)
    def test_invalid_resize_volume_size(self):
        self.controller._validate_resize(self.resize_body, 2)

    @raises(exception.BadRequest)
    def test_invalid_resize_volume_size2(self):
        self.controller._validate_resize(self.resize_body, 5.2)

    @raises(exception.BadRequest)
    def test_invalid_resize_volume_size3(self):
        self.controller._validate_resize(self.resize_body, 'a')

    @raises(exception.OverLimit)
    def test_resize_too_large(self):
        body = {'resize': {'volume': {'size': 1024 * 1024 * 1024}}}
        self.controller._validate_resize(body, 2)

    @raises(exception.BadRequest)
    def test_resize_volume_no_size(self):
        body = {'resize': {'volume': {}}}
        self.controller._validate_resize(body, 1)

    @raises(exception.BadRequest)
    def test_resize_no_volume(self):
        body = {'resize': {}}
        self.controller._validate_resize(body, 1)

    def test_valid_single_resize_in_body(self):
        body = {'resize': {'flavorRef': 2}}
        self.controller._validate_single_resize_in_body(body)

    def test_valid_resize_flavor(self):
        body = {'resize': {'flavorRef': 2}}
        self.controller._validate_resize_instance(body)

    @raises(exception.BadRequest)
    def test_resize_flavor_no_size(self):
        body = {'resize': {'flavorRef': {}}}
        self.controller._validate_resize(body, 1)

    @raises(exception.BadRequest)
    def test_resize_flavor_and_volume_invalid(self):
        body = {'resize': {'flavorRef': 2,'volume': {'size': 2}}}
        self.controller._validate_single_resize_in_body(body)

    @raises(exception.BadRequest)
    def test_resize_flavor_and_volume_invalid2(self):
        body = {'resize': {'flavorRef': 2,'volume': {}}}
        self.controller._validate_resize(body, 1)

    @raises(exception.BadRequest)
    def test_single_resize_invalid(self):
        body = {'flavorRef': 2,'volume': {}}
        self.controller._validate_single_resize_in_body(body)

    @raises(exception.BadRequest)
    def test_resize_instance_invalid2(self):
        body = {'flavorRef': 2,'volume': {}}
        self.controller._validate_resize_instance(body)

    @raises(exception.BadRequest)
    def test_resize_invalid3(self):
        body = {'flavorRef': 2,'volume': {}}
        self.controller._validate(body)

    @raises(exception.BadRequest)
    def test_resize_invalid4(self):
        body = {'instance': {'flavorRef': 2,'volume': {}}}
        self.controller._validate(body)

    @raises(exception.BadRequest)
    def test_validate_volume_size_bad(self):
        self.controller._validate_volume_size('a')

    @raises(exception.BadRequest)
    def test_validate_volume_size_bad2(self):
        self.controller._validate_volume_size(-1)

    @raises(exception.OverLimit)
    def test_validate_volume_size_bad3(self):
        self.controller._validate_volume_size(9999999)

    def test_valid_instance_restart(self):
        self.controller._validate_restart_instance(1, vm_states.ACTIVE)

    @raises(exception.UnprocessableEntity)
    def test_invalid_instance_restart(self):
        self.controller._validate_restart_instance(1, vm_states.BUILDING)

