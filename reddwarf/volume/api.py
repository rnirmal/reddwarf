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

"""
Handles all requests relating to volumes.
"""

from nova import exception
from nova import flags
from nova import log as logging
from nova import rpc
from nova.volume import api as nova_volume_api


FLAGS = flags.FLAGS

LOG = logging.getLogger('reddwarf.volume')


class API(nova_volume_api.API):
    """Modified Volume API supporting reddwarf specific features"""

    def assign_to_compute(self, context, volume_id, host):
        rpc.cast(context,
                 FLAGS.scheduler_topic,
                 {"method": "assign_volume",
                  "args": {"topic": FLAGS.volume_topic,
                           "volume_id": volume_id,
                           "host": host}})

    def delete_volume_when_available(self, context, volume_id, time_out):
        host = self.get(context, volume_id)['host']
        rpc.cast(context,
                 self.db.queue_get_for(context, FLAGS.volume_topic, host),
                 {"method": "delete_volume_when_available",
                  "args": {"volume_id": volume_id,
                           "time_out": time_out}})

    def check_for_available_space(self, context, size):
        """Check the device for available space for a Volume"""
        #TODO(cp16net) scheduler does not support rpc call with scheduler topic
        # scheduler changes the rpc call to a cast when forwarding the msg.
        # We will have to revisit this when we add multiple volume managers.
        return rpc.call(context,
                         FLAGS.volume_topic,
                         {"method": "check_for_available_space",
                          "args": {'size': size}})

    def get_storage_device_info(self, context):
        """Returns the storage device information for Admins."""
        if context.is_admin:
            LOG.debug("calling the method get_storage_device_info")
            return rpc.call(context,
                             FLAGS.volume_topic,
                             {"method": "get_storage_device_info",
                              "args": {}})
        raise exception.AdminRequired()

    def unassign_from_compute(self, context, volume_id, host):
        rpc.cast(context,
                 FLAGS.scheduler_topic,
                 {"method": "unassign_volume",
                  "args": {"topic": FLAGS.volume_topic,
                           "volume_id": volume_id,
                           "host": host}})
