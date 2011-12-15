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
from nose.tools import raises

from nova import context
from nova import exception
from nova import flags
from nova import test
from nova import utils
from nova.compute import power_state
from nova.compute import vm_states
from nova.db import api as db_api

from reddwarf.tests import util
from reddwarf.reaper.driver import ReddwarfReaperDriver


ORPHAN_TIME_OUT = 24 * 60 * 60
FLAGS = flags.FLAGS


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


class TestReapingInstancesHungInBuild(test.TestCase):

    def setUp(self):
        super(TestReapingInstancesHungInBuild, self).setUp()
        self.context = context.get_admin_context()
        self.reaper_driver = ReddwarfReaperDriver()
        self.timeout = FLAGS.reddwarf_reaper_instance_build_timeout

    def tearDown(self):
        super(TestReapingInstancesHungInBuild, self).tearDown()

    def _create_instance(self, id, power_state, vm_state, time_shift=0,
                               deleted=0):
        possible_reap_time = utils.utcnow() - timedelta(seconds=self.timeout)
        values = {
            'created_at': possible_reap_time + timedelta(seconds=time_shift),
            'deleted': deleted,
            'id': id,
            'power_state': power_state,
            'vm_state': vm_state,
            }
        db_api.instance_create(self.context, values)

    def _assert_failed(self, instance_ref):
        self.assertEqual(instance_ref['power_state'], power_state.FAILED)
        self.assertEqual(instance_ref['vm_state'], vm_states.ERROR)
        self.assertEqual(instance_ref['deleted'], 0)

    def _assert_no_change(self, instance_ref, power_state, vm_state, deleted=0):
        self.assertEqual(instance_ref['power_state'], power_state)
        self.assertEqual(instance_ref['vm_state'], vm_state)
        self.assertEqual(instance_ref['deleted'], deleted)

    def test_reaping_power_state_NOSTATE(self):
        id = 1111
        self._create_instance(id, power_state.NOSTATE, vm_states.BUILDING)
        self.reaper_driver.periodic_tasks(self.context)
        instance_ref = db_api.instance_get(self.context, id)
        self._assert_failed(instance_ref)

    def test_reaping_power_state_BUILDING(self):
        id = 1112
        self._create_instance(id, power_state.BUILDING, vm_states.BUILDING)
        self.reaper_driver.periodic_tasks(self.context)
        instance_ref = db_api.instance_get(self.context, id)
        self._assert_failed(instance_ref)

    @raises(exception.InstanceNotFound)
    def test_not_reaping_deleted(self):
        id = 1113
        self._create_instance(id, power_state.SHUTDOWN, vm_states.DELETED,
                              deleted=1)
        self.reaper_driver.periodic_tasks(self.context)
        db_api.instance_get(self.context, id)

    def test_not_reaping_before_timeout(self):
        id = 1114
        self._create_instance(id, power_state.BUILDING, vm_states.BUILDING,
                              time_shift=60)
        self.reaper_driver.periodic_tasks(self.context)
        instance_ref = db_api.instance_get(self.context, id)
        self._assert_no_change(instance_ref, power_state.BUILDING,
                               vm_states.BUILDING)

    def test_not_repeaping_power_state_RUNNING(self):
        id = 1115
        self._create_instance(id, power_state.RUNNING, vm_states.BUILDING)
        self.reaper_driver.periodic_tasks(self.context)
        instance_ref = db_api.instance_get(self.context, id)
        self._assert_no_change(instance_ref, power_state.RUNNING,
                               vm_states.BUILDING)
