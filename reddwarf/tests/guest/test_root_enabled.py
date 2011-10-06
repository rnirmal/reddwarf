# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright (c) 2011 OpenStack, LLC.
# All Rights Reserved.
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

from datetime import timedelta
from nova import compute
from nova import context
from nova.db import api as nova_db_api
from reddwarf.db import api as rd_db_api
#from reddwarf.db import migration
from nova.guest.api import API as guest_api
from nova import test
from nova import utils

database_file = "reddwarf_test.sqlite"
sql_connection = "sqlite:///%s" % database_file
current_version = 4

class TestWhenEnablingRoot(test.TestCase):

    def setUp(self):
        super(TestWhenEnablingRoot, self).setUp()
        self.context = context.get_admin_context()
        self.guest_api = guest_api()
        self.rd_db_api = rd_db_api
        self.instance_id = 1
        #migration.db_upgrade(sql_connection, 4)

    def tearDown(self):
        super(TestWhenEnablingRoot, self).tearDown()

    def testATHING(self):
        #result = self.guest_api.enable_root(self.context, self.instance_id)
        ctxt = self.context
        res1 = self.rd_db_api.record_root_enabled_timestamp(ctxt, self.instance_id)
        print res1.root_enabled_at, res1.instance_id
        res2 = self.rd_db_api.get_root_enabled_timestamp(ctxt, self.instance_id)
        print res2.root_enabled_at, res2.instance_id
        assert res1 == res2


    def test_root_in_order(self):
        # Pretend to create the container. Root doesn't exist.
        # Enable root. Root now exists.
        # Disable root. YOU CAN'T. Root still exists.
        # Reset root. Root still exists, and hasn't changed.
        # Enable root again. Root still still exists, and still hasn't changed.
        pass