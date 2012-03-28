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
Tests for reddwarf.volume.manager.
"""

from nose.tools import raises

import nova
from nova import context
from nova import flags
from nova import test
from nova import utils
import reddwarf
from reddwarf import exception


FLAGS = flags.FLAGS


def volume_get_inuse(ctxt, id):
    return {'status': 'in-use',
            'id': 1,
            }

def volume_get_available(ctxt, id):
    return {'status': 'available',
            'id': 1,
            }

def volume_get_error(ctxt, id):
    return {'status': 'error',
            'id': 1,
            }

def delete_volume(self, ctxt, id):
    return

class VolumeManagerDeleteWhenAvailableTest(test.TestCase):
    """Tests the delete_volume_when_available method of reddwarf.volume.manager."""


    def setUp(self):
        super(VolumeManagerDeleteWhenAvailableTest, self).setUp()
        self.flags(volume_manager="reddwarf.volume.manager.ReddwarfVolumeManager")
        self.volume_manager = utils.import_object(FLAGS.volume_manager)
        self.context = context.get_admin_context()
        self.volume_id = 1
        self.stubs.Set(reddwarf.volume.manager.ReddwarfVolumeManager, "delete_volume", delete_volume)

    def tearDown(self):
        super(VolumeManagerDeleteWhenAvailableTest, self).tearDown()

    @raises(exception.PollTimeOut)
    def test_delete_volume_when_inuse(self):
        self.stubs.Set(nova.db.api, "volume_get", volume_get_inuse)
        self.volume_manager.delete_volume_when_available(self.context, self.volume_id, 1)

    def test_delete_volume_when_available(self):
        self.stubs.Set(nova.db.api, "volume_get", volume_get_available)
        self.volume_manager.delete_volume_when_available(self.context, self.volume_id, 1)

    def test_delete_volume_when_error(self):
        self.stubs.Set(nova.db.api, "volume_get", volume_get_error)
        self.volume_manager.delete_volume_when_available(self.context, self.volume_id, 1)
