#    Copyright 2012 OpenStack LLC
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

from nova import exception
from nova import flags
from nova import log as logging
from nova import rpc
from nova.compute import api as nova_compute_api
from nova.compute import task_states
from nova.compute import vm_states
from nova.scheduler import api as scheduler_api


FLAGS = flags.FLAGS

LOG = logging.getLogger(__name__)


class API(nova_compute_api.API):
    """Modified Compute API supporting reddwarf specific features"""

    def __init__(self, *args, **kwargs):
        super(API, self).__init__(*args, **kwargs)

    def resize_volume(self, context, volume_id):
        """
        Rescan and resize the attached volume filesystem once the actual volume
        resizing has been completed.
        """
        context = context.elevated()
        instance = self.db.volume_get_instance(context, volume_id)
        if not instance:
            raise exception.Error(_("Volume isn't attached to anything!"))
        rpc.cast(context,
                 self.db.queue_get_for(context, FLAGS.compute_topic,
                                       instance['host']),
                 {"method": "resize_volume",
                 "args": {"instance_id": instance['id'],
                          "volume_id": volume_id}})

    @scheduler_api.reroute_compute("restart")
    def restart(self, context, instance_id):
        """Reboot the given instance."""
        self.update(context,
                    instance_id,
                    vm_state=vm_states.ACTIVE,
                    task_state=task_states.REBOOTING)
        self._cast_compute_message('restart', context, instance_id)
