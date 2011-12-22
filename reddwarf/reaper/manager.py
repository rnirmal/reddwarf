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

import sys

from nova import flags
from nova import log as logging
from nova import manager
from nova import utils
from reddwarf.reaper import driver

FLAGS = flags.FLAGS
flags.DEFINE_string('reaper_driver', 'nova.reaper.driver.ReaperDriver',
                    'Driver run with the Reaper.')

LOG = logging.getLogger('nova.reaper.manager')


class ReaperManager(manager.SchedulerDependentManager):

    def __init__(self, reaper_driver=None, *args, **kwargs):
        super(ReaperManager, self).__init__(service_name="reaper",
                                             *args, **kwargs)
        if not reaper_driver:
            reaper_driver = FLAGS.reaper_driver
        try:
            self.driver = utils.import_object(reaper_driver)
        except ImportError as e:
            LOG.error("Unable to load the Reaper driver: %s" % e)
            sys.exit(1)

    def init_host(self):
        pass

    def periodic_tasks(self, context=None):
        """Tasks to be run at a periodic interval."""
        super(ReaperManager, self).periodic_tasks(context)
        self.driver.periodic_tasks(context)
