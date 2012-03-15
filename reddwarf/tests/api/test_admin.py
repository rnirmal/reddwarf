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
import time
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

FAKE_CONTEXT = {'user': 'admin', 'role': 'admin'}
FAKE_INSTANCE = {'id': 102}
FAKE_DB_LIST = [
    {'_name': 'foobar',
     '_collate': 'utf8_general_ci',
     '_character_set': 'utf8'},
    {'_name': 'mysql',
     '_collate': 'latin1_swedish_ci',
     '_character_set': 'latin1'}
]
FAKE_USER_LIST = [
    {'_name': 'foobar'},
    {'_name': 'root'}
]

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

    def test_get_guest_info_no_dbs(self):
        # Instantiate the controller because we need to inject mocked
        # attributes and methods
        controller = reddwarf.api.management.Controller()

        # We may need to do this a different way but for the purposes of just
        # testing this code flow it should suffice.
        root_enabled = mox.MockAnything()
        created_at = int(time.time())
        root_enabled.created_at = created_at
        root_enabled.user_id = 'admin'

        # Just some mock goodness
        status = mox.MockAnything()
        status.is_sql_running = False
        self.mox.StubOutWithMock(reddwarf.api.management.dbapi,
                                 'get_root_enabled_history')
        reddwarf.api.management.dbapi.get_root_enabled_history(
            FAKE_CONTEXT, FAKE_INSTANCE['id']).AndReturn(root_enabled)

        self.mox.ReplayAll()
        instance = controller._get_guest_info(FAKE_CONTEXT,
                                              FAKE_INSTANCE['id'],
                                              status,
                                              FAKE_INSTANCE)
        self.assertTrue(isinstance(instance['databases'], list))
        self.assertTrue(isinstance(instance['users'], list))
        self.assertTrue(len(instance['databases']) == 0)
        self.assertTrue(len(instance['users']) == 0)
        self.assertEqual(root_enabled.created_at, instance['root_enabled_at'])
        self.assertEqual(root_enabled.user_id, instance['root_enabled_by'])

    def test_get_guest_info_dbs(self):
        # Instantiate the controller because we need to inject mocked
        # attributes and methods
        controller = reddwarf.api.management.Controller()

        # We may need to do this a different way but for the purposes of just
        # testing this code flow it should suffice.
        root_enabled = mox.MockAnything()
        created_at = int(time.time())
        root_enabled.created_at = created_at
        root_enabled.user_id = 'admin'

        # Just some mock goodness
        status = mox.MockAnything()
        status.is_sql_running = True
        self.mox.StubOutWithMock(controller.guest_api, 'list_databases')
        controller.guest_api.list_databases(FAKE_CONTEXT,
                                            FAKE_INSTANCE['id'])\
            .AndReturn(FAKE_DB_LIST)
        self.mox.StubOutWithMock(controller.guest_api, 'list_users')
        controller.guest_api.list_users(FAKE_CONTEXT,
                                        FAKE_INSTANCE['id'])\
            .AndReturn(FAKE_USER_LIST)
        self.mox.StubOutWithMock(reddwarf.api.management.dbapi,
                                 'get_root_enabled_history')
        reddwarf.api.management.dbapi.get_root_enabled_history(
            FAKE_CONTEXT, FAKE_INSTANCE['id']).AndReturn(root_enabled)

        self.mox.ReplayAll()
        instance = controller._get_guest_info(FAKE_CONTEXT,
                                              FAKE_INSTANCE['id'],
                                              status,
                                              FAKE_INSTANCE)
        self.assertTrue(isinstance(instance['databases'], list))
        self.assertTrue(isinstance(instance['users'], list))
        self.assertTrue(len(instance['databases']) >= 0)
        self.assertTrue(len(instance['users']) >= 0)
        self.assertEqual(root_enabled.created_at, instance['root_enabled_at'])
        self.assertEqual(root_enabled.user_id, instance['root_enabled_by'])