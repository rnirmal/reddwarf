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
from nova import context
from nova.db import api as db_api
from nova import test
from nova import utils
from reddwarf.reaper.driver import ReddwarfReaperDriver


ORPHAN_TIME_OUT = 24 * 60 * 60


class FakeVolumeApi(object):

    def __init__(self):
        self.deleted_volumes = []

    def delete(self, context, volume):
        self.deleted_volumes.append(volume)
    

class TestWhenAVolumeIsOrphaned(test.TestCase):

    def setUp(self):
        super(TestWhenAVolumeIsOrphaned, self).setUp()
        self.context = context.get_admin_context()
        self.reaper_driver = ReddwarfReaperDriver(ORPHAN_TIME_OUT)
        self.reaper_driver.volume_api = FakeVolumeApi()
        self.new_volume = self.create_orphaned_volume()

    def tearDown(self):
        db_api.volume_destroy(self.context, self.new_volume['id'])

        super(TestWhenAVolumeIsOrphaned, self).tearDown()

    def create_orphaned_volume(self):
        options = {
            'size': 1,
            'user_id': self.context.user_id,
            'project_id': self.context.project_id,
            'snapshot_id': None,
            'availability_zone': None,
            'status': "available",  # !!
            'attach_status': "detached",
            'display_name': 'blah',
            'display_description': "test volume",
            'volume_type_id': None,
            'metadata': None,
            }
        return db_api.volume_create(self.context, options)


    def test_an_old_orphan_is_reaped(self):
        volume_id = self.new_volume['id']
        updated_at = utils.utcnow() - timedelta(seconds=ORPHAN_TIME_OUT * 2)
        db_api.volume_update(self.context, volume_id,
                             {'updated_at':updated_at})
        self.reaper_driver.periodic_tasks(self.context)
        self.assertEqual(len(self.reaper_driver.volume_api.deleted_volumes), 1)

    def test_an_new_orphan_is_left_alone(self):
        self.reaper_driver.periodic_tasks(self.context)
        self.assertEqual(len(self.reaper_driver.volume_api.deleted_volumes), 0)
