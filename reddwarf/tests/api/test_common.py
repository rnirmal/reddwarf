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

from nose.tools import raises

from nova import test

from reddwarf.api import common


class ApiCommonTest(test.TestCase):
    """Test common api functions"""

    def setUp(self):
        super(ApiCommonTest, self).setUp()

    def tearDown(self):
        super(ApiCommonTest, self).tearDown()

    def test_populate_user(self):
        users = [{'name': 'test', 'password': 'password'}]
        users_data = common.populate_users(users)
        self.assertEqual(len(users_data), 1)
        user = users_data[0]
        self.assertEqual(user['_name'], "test")
        self.assertEqual(user['_password'], "password")

    def test_populate_users(self):
        users = [{'name': 'test', 'password': 'password'},
                 {'name': 'user2', 'password': 'test2'}]
        users_data = common.populate_users(users)
        self.assertEqual(len(users_data), 2)
        user1 = users_data[0]
        user2 = users_data[1]
        self.assertEqual(user1['_name'], "test")
        self.assertEqual(user1['_password'], "password")
        self.assertEqual(user2['_name'], "user2")
        self.assertEqual(user2['_password'], "test2")

    def test_populate_user_database_old_format(self):
        users = [{'name': 'test', 'password': 'password', 'database': 'tdb'}]
        users_data = common.populate_users(users)
        self.assertEqual(len(users_data), 1)
        user = users_data[0]
        self.assertEqual(user['_name'], "test")
        self.assertEqual(user['_password'], "password")
        self.assertEqual(len(user.get('_databases', '')), 0)

    def test_populate_user_databases(self):
        body = {'users': [{'name': 'test', 'password': 'password',
                           'databases': [{'name': 'tdb'}, {'name': 'tdb1'}]}]}
        users_data = common.populate_users(body.get("users"))
        self.assertEqual(len(users_data), 1)
        user = users_data[0]
        self.assertEqual(user['_name'], "test")
        self.assertEqual(user['_password'], "password")
        self.assertEqual(len(user['_databases']), 2)
        self.assertEqual(user['_databases'][0]['_name'], "tdb")
        self.assertEqual(user['_databases'][1]['_name'], "tdb1")
