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
Tests the configuration API
"""

import json
import webob
from paste import urlmap
from nose.tools import raises
from webob import exc

from nova import context
from nova import exception
from nova import flags
from nova import test
from nova.api.openstack import faults

from reddwarf.api import config
from reddwarf.db import api as dbapi
from reddwarf.tests import util


FLAGS = flags.FLAGS

test_key = "reddwarf_imageref"
test_value = "2"
test_desc = "reddwarf image"
new_value = "5"
test_config = {'key': test_key, 'value': test_value, 'description': test_desc}
update_config = {'key': test_key, 'value': new_value, 'description': test_desc}


def request_obj(url, method, body):
    req = webob.Request.blank(url)
    req.method = method
    req.body = json.dumps(body)
    req.headers["content-type"] = "application/json"
    return req


class ConfigApiTest(test.TestCase):
    """Test various configuration update scenarios"""

    def setUp(self):
        super(ConfigApiTest, self).setUp()
        self.context = context.get_admin_context()
        self.controller = config.Controller()

    def test_000_reset(self):
        util.reset_database()
        util.db_sync()

    def test_config_create(self):
        body = {'configs': [test_config]}
        req = request_obj('/v1.0/mgmt/configs', 'POST', body)
        res = req.get_response(util.wsgi_app(fake_auth_context=self.context))
        self.assertEqual(res.status_int, 200)
        result = dbapi.config_get(test_key)

        self.assertEqual(test_key, result.key)
        self.assertEqual(test_value, result.value)
        self.assertEqual(test_desc, result.description)

    def test_config_create_duplicate(self):
        body = {'configs': [test_config]}
        req = request_obj('/v1.0/mgmt/configs', 'POST', body)

        res = req.get_response(util.wsgi_app(fake_auth_context=self.context))
        self.assertEqual(res.status_int, 500)
        expected_msg = "Configuration %s already exists." % test_key
        res_body = json.loads(res.body)
        self.assertEqual(res_body['cloudServersFault']['message'], expected_msg)

    def test_config_create_invalid(self):
        body = {'configs': [test_config]}
        req = request_obj('/v1.0/mgmt/configs', 'POST', body)

        res = req.get_response(util.wsgi_app(fake_auth_context=self.context))
        self.assertEqual(res.status_int, 500)
        expected_msg = "Configuration %s already exists." % test_key
        res_body = json.loads(res.body)
        self.assertEqual(res_body['cloudServersFault']['message'], expected_msg)

    def test_config_list(self):
        body = {'configs':
                    [{'key': 'test1', 'value': 'test1val'},
                     {'key': 'test2', 'value': 'test2val'},
                     {'key': 'test3', 'value': 'test3val'}]
               }
        req = request_obj('/v1.0/mgmt/configs', 'POST', body)
        res = req.get_response(util.wsgi_app(fake_auth_context=self.context))
        self.assertEqual(res.status_int, 200)

        req1 = webob.Request.blank('/v1.0/mgmt/configs')
        res = req1.get_response(util.wsgi_app(fake_auth_context=self.context))
        for item in body['configs']:
            item['description'] = None
        body['configs'].append(test_config)

        self.assertDictListMatch(sorted(body['configs']),
                                 sorted(json.loads(res.body)['configs']))

    def test_config_get(self):
        req = webob.Request.blank('/v1.0/mgmt/configs/%s' % test_key)
        res = req.get_response(util.wsgi_app(fake_auth_context=self.context))
        self.assertDictMatch(json.loads(res.body)['config'], test_config)

    def test_config_get_invalid(self):
        invalid_key = "transdffs"
        expected_msg = "Configuration %s not found." % invalid_key
        req = webob.Request.blank('/v1.0/mgmt/configs/%s' % invalid_key)
        res = req.get_response(util.wsgi_app(fake_auth_context=self.context))
        self.assertEqual(res.status_int, 500)
        res_body = json.loads(res.body)
        self.assertEqual(res_body['cloudServersFault']['message'], expected_msg)

    def test_config_update(self):
        old_value = dbapi.config_get(test_key).value
        self.assertNotEqual(new_value, old_value)
        body = {'config': update_config}
        req = request_obj('/v1.0/mgmt/configs/%s' % test_key, 'PUT', body)

        res = req.get_response(util.wsgi_app(fake_auth_context=self.context))
        self.assertEqual(res.status_int, 200)
        result = dbapi.config_get(test_key)
        self.assertEqual(new_value, result.value)

    def test_config_zdelete(self):
        req = webob.Request.blank('/v1.0/mgmt/configs/%s' % test_key)
        req.method = 'DELETE'
        res = req.get_response(util.wsgi_app(fake_auth_context=self.context))
        self.assertEqual(res.status_int, 200)

        req1 = webob.Request.blank('/v1.0/mgmt/configs/%s' % test_key)
        res = req1.get_response(util.wsgi_app(fake_auth_context=self.context))

    def test_config_zdelete_nonexistent(self):
        nonexistent = "nonexistent"
        req = webob.Request.blank('/v1.0/mgmt/configs/%s' % nonexistent)
        req.method = 'DELETE'
        res = req.get_response(util.wsgi_app(fake_auth_context=self.context))
        self.assertEqual(res.status_int, 200)

    def test_config_validate_empty_body(self):
        req = request_obj('/v1.0/mgmt/configs', 'POST', "")
        res = req.get_response(util.wsgi_app(fake_auth_context=self.context))
        self.assertEqual(res.status_int, 422)
        res_body = json.loads(res.body)
        expected_msg = "Unable to process the contained instructions"
        self.assertEqual(res_body['cloudServersFault']['message'], expected_msg)

    @raises(exception.ApiError)
    def test_config_validate_create_no_configs(self):
        body = {'config': {'key': test_key}}
        self.controller._validate_create(body)

    @raises(exception.ApiError)
    def test_config_validate_create_no_key(self):
        body = {'configs': [{'keys': test_key}]}
        self.controller._validate_create(body)

    @raises(exception.ApiError)
    def test_config_validate_update_no_config(self):
        body = {'configs': {'key': test_key}}
        self.controller._validate_update(body)

    @raises(exception.ApiError)
    def test_config_validate_update_no_key(self):
        body = {'config': {'keys': test_key}}
        self.controller._validate_update(body)
