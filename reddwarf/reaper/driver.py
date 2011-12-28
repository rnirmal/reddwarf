# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright (c) 2011 Openstack, LLC.
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

from nova import flags
from nova import log as logging
from nova import volume
from nova import utils
from reddwarf.db import api as reddwarf_db


FLAGS = flags.FLAGS
LOG = logging.getLogger(__name__)


flags.DEFINE_integer('reddwarf_reaper_orphan_volume_expiration_time',
                     60 * 60 * 24 * 7,
                     'Time until reaper will destroy orphaned volumes.')


class ReaperDriver(object):

    def periodic_tasks(self, context):
        pass


class ReddwarfReaperDriver(object):
    """
    Searches for failed resources.
    """
    def __init__(self, orphan_time_out=None):
        self.volume_api = volume.API()
        self.orphan_time_out = orphan_time_out or \
            FLAGS.reddwarf_reaper_orphan_volume_expiration_time

    def clean_up_volumes(self, context):
        """Finds all volumes which are not associated to an instance."""
        expiration_time = self.orphan_time_out
        latest_valid_time = utils.utcnow() - timedelta(seconds=expiration_time)
        LOG.debug("Preparing to delete orphaned volumes updated before %s" %
                  latest_valid_time)
        volumes = reddwarf_db.volume_get_orphans(context, latest_valid_time)
        if volumes:
            for volume_ref in volumes:
                self.volume_api.delete(context, volume_ref['id'])
                LOG.warn("Deleting an orphaned volume, %s with description %s" %
                         (volume_ref['id'], volume_ref['display_description']))

    def periodic_tasks(self, context):
        self.clean_up_volumes(context)
