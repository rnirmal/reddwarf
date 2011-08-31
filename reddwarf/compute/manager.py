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

import json

from nova import flags
from nova import log as logging
from nova.api.platform.dbaas import common
from nova.compute import power_state
from nova.guest import api as guest_api
from nova.notifier import api as notifier
from nova import utils

from nova.compute.manager import ComputeManager as NovaComputeManager

from reddwarf.db import api as dbapi

flags.DEFINE_integer('reddwarf_guest_initialize_time_out', 10 * 60,
                     'Time in seconds for a guest to initialize before it is '
                     'considered a failure and aborted.')
flags.DEFINE_integer('reddwarf_instance_suspend_time_out', 3 * 60,
                     'Time in seconds for a compute instance to suspend '
                     'during when aborted before a PollTimeOut is raised.')

FLAGS = flags.FLAGS
LOG = logging.getLogger(__name__)
VALID_ABORT_STATES = [
    power_state.CRASHED,
    power_state.FAILED,
    power_state.PAUSED,
    power_state.SUSPENDED,
    power_state.SHUTDOWN
]

def publisher_id(host=None):
    return notifier.publisher_id("reddwarf-compute", host)


class ComputeManager(NovaComputeManager):
    """Manages the running instances from creation to destruction."""

    def __init__(self, *args, **kwargs):
        super(ComputeManager, self).__init__(*args, **kwargs)
        self.guest_api = guest_api.API()

    def abort_instance(self, context, instance_id):
        """Stops an instance and marks the guest status as FAILED."""
        dbapi.guest_status_update(instance_id, power_state.FAILED)
        LOG.audit(_("Aborting db instance %d.") % instance_id, context=context)
        self.suspend_instance(context, instance_id)

        # Wait for the state has become suspended so we know the guest won't
        # wake up and change its state. All the while until the end, set
        # the state to failed (in reality the suspension should occur quickly
        # and normally we will not be aborting because we didn't wait
        # long enough).

        def get_instance_state():
            return self.db.instance_get(context, instance_id).state

        def confirm_state_is_suspended(instance_state):
            # Make sure the guest state is set to FAILED, in wakes up and
            # tries anything here.
            dbapi.guest_status_update(instance_id, power_state.FAILED)
            return instance_state in VALID_ABORT_STATES

        utils.poll_until(get_instance_state,
                         confirm_state_is_suspended,
                         sleep_time=1,
                         time_out=FLAGS.reddwarf_instance_suspend_time_out)


    def _find_requested_databases(self, context, instance_id):
        """Get the databases to create along with this container."""
        #TODO(tim.simpson) Grab the metadata only once and get the volume info
        #                  at the same time.
        metadata = self.db.instance_metadata_get(context, instance_id)
        # There shouldn't be exceptions coming from below mean the dbcontainers
        # REST API is misbehaving and sending invalid data.
        databases_list = json.loads(metadata['database_list'])
        return common.populate_databases(databases_list)

    def _initialize_compute_instance(self, context, instance_id, **kwargs):
        """Runs underlying compute instance and aborts if any errors occur."""
        try:
            super(ComputeManager, self)._run_instance(context, instance_id,
                                                      **kwargs)
        except Exception as e:
            LOG.audit(_("Aborting instance %d because the underlying compute "
                        "instance failed to run.") % instance_id,
                      context=context)
            LOG.error(e)
            self.abort_instance(context, instance_id)
            raise

    def _initialize_guest(self, context, instance_id, databases):
        """Tell the guest to initialize itself and wait for it to happen.

        This method aborts the guest if there's a timeout.

        """
        try:
            self.guest_api.prepare(context, instance_id, databases)
            utils.poll_until(lambda : dbapi.guest_status_get(instance_id),
                             lambda status : status == power_state.RUNNING,
                             sleep_time=2,
                             time_out=FLAGS.reddwarf_guest_initialize_time_out)
        except utils.PollTimeOut:
            LOG.audit(_("Aborting instance %d because the guest did not "
                        "initialize.") % instance_id, context=context)
            self.abort_instance(context, instance_id)
            raise

    def _run_instance(self, context, instance_id, **kwargs):
        """Launch a new instance with specified options."""
        databases = self._find_requested_databases(context, instance_id)
        # TODO(tim.simpson): Create volume here via rpc call.
        self._initialize_compute_instance(context, instance_id, **kwargs)
        self._initialize_guest(context, instance_id, databases)
