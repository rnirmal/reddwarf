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

base_url = util.v1_prefix
mgmt_url = util.v1_mgmt_prefix

def images_show(self, req, id):
    return {'image': {'id': id, 'name': id}}


class MgmtApiTest(test.TestCase):
    """Test various Database Management API calls"""

    def setUp(self):
        super(MgmtApiTest, self).setUp()
        self.context = context.RequestContext('fake', 'fake', 
                                              auth_token=True, is_admin=False)

    def tearDown(self):
        self.stubs.UnsetAll()
        super(MgmtApiTest, self).tearDown()

    def _test_path_restricted(self, path, method='GET'):
        req = webob.Request.blank(mgmt_url + path)
        res = req.get_response(util.wsgi_app(fake_auth_context=self.context))
        self.assertEqual(res.status_int, 401)
        res_body = json.loads(res.body)
        expected = "User does not have admin privileges."
        self.assertEqual(res_body['unauthorized']['message'], expected)

    def test_host_restricted(self):
        self._test_path_restricted('hosts/1')

    def test_hosts_restricted(self):
        self._test_path_restricted('hosts')

    def test_images_available_to_admin(self):
        self.stubs.Set(nova.api.openstack.images.Controller,
                       "show", images_show)
        req = webob.Request.blank(base_url + '/images/1')
        admin_context = context.RequestContext('fake', 'fake', 
                                              auth_token=True, is_admin=True)
        res = req.get_response(util.wsgi_app(fake_auth_context=admin_context))
        self.assertEqual(res.status_int, 200)
        res_body = json.loads(res.body)
        print res_body
        self.assertTrue(len(res_body) == 1)

    def test_images_restricted(self):
        req = webob.Request.blank(base_url + '/images/1')
        res = req.get_response(util.wsgi_app(fake_auth_context=self.context))
        self.assertEqual(res.status_int, 401)
        res_body = json.loads(res.body)
        expected = "User does not have admin privileges."
        self.assertEqual(res_body['unauthorized']['message'], expected)

    def test_instance_restricted(self):
        self._test_path_restricted('instances/1')

    def test_storage_restricted(self):
        self._test_path_restricted('storage')

    def test_accounts_restricted(self):
        self._test_path_restricted('accounts/1')

    def test_root_restricted(self):
        self._test_path_restricted('instances/1/root')

    def test_instances_index_restricted(self):
        self._test_path_restricted('instances')
