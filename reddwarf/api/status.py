# Copyright 2012 OpenStack LLC.
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
Common database instance status code used across DBaaS API.
"""
import types

from nova import log as logging
from nova.api.openstack import common
from nova import db

from reddwarf.db import api as dbapi
from reddwarf.guest import status as guest_statuses
from reddwarf.exception import NotFound
from reddwarf.exception import UnprocessableEntity
from reddwarf.guest.status import GuestStatus

LOG = logging.getLogger('reddwarf.api.status')


class InstanceStatus(object):
    """The authoritative source of a Reddwarf Instance status."""
    
    def __init__(self, 
                guest_state=None,
                guest_status_debug_info=None,
                server_status=None,
                ):
        if guest_state:
            self.guest_status = GuestStatus.from_code(guest_state)
        else:
            self.guest_status = guest_statuses.SHUTDOWN
        self.guest_status_debug_info = guest_status_debug_info
        # TODO(ed-): incorporate volume status.
        self.server_status = server_status or guest_statuses.SHUTDOWN.description
        assert isinstance(self.server_status, types.StringTypes)

    @staticmethod
    def load_from_db(context, instance_id):
        """Loads everything from the database to find an InstanceStatus.

        If multiple instances must be found, it's more efficient to create an
        InstanceStatusLookup which will load all guest states in one db call
        and and return an object which will return an InstanceStatus when given
        an instance_ref or cloud server dictionary from the REST api code.

        """
        local_id = dbapi.localid_from_uuid(instance_id)
        lookup = InstanceStatusLookup([local_id])
        return lookup.get_status_from_id(context, local_id)

    @property
    def is_sql_running(self):
        responsive = [
            guest_statuses.RUNNING,
            ]
        return self.guest_status in responsive

    def can_perform_action_on_instance(self):
        """
        Checks if the instance is in a state where an action can be performed.
        """
        valid_action_states = ['ACTIVE']
        if self.status not in valid_action_states:
            msg = "Instance is not currently available for an action to be performed. Status [%s]" % self.status
            LOG.debug(msg)
            raise UnprocessableEntity(msg)

    @property
    def status(self):
        if self.server_status in ["ERROR", "REBOOT", "RESIZE"]:
            return self.server_status
        # TODO(ed-) Possibly a mapping error resulting in this function
        # returning a None. Should raise an exception instead
        if guest_statuses.PAUSED == self.guest_status: # Use GuestStatus' smarter comparator.
            return "REBOOT"
        return self.guest_status.api_status

    def get_guest_status(self):
        """Build out the guest status information"""
        result = {}
        if self.guest_status_debug_info is not None:
            debug = self.guest_status_debug_info
            result['created_at'] = debug.created_at
            result['deleted'] = debug.deleted
            result['deleted_at'] = debug.deleted_at
            result['instance_id'] = debug.instance_id
            result['state'] =debug.state
            result['state_description'] = debug.state_description
            result['updated_at'] = debug.updated_at
        return result


class InstanceStatusLookup(object):
    """
    Stores several guest states to avoid looking them up each call, and can
    quickly return InstanceStatus objects when given the compute instance
    component.
    """
    def __init__(self, guest_ids):
        self.local_ids = guest_ids
        lookup = dbapi.guest_status_get_list(self.local_ids).all()
        self.guest_status_mapping = dict([(r.instance_id, r) for r in lookup])

    def get_status_from_id(self, context, id):
        """Loads a compute instance ref to grab the instance status."""
        instance_ref = db.instance_get(context, id)
        return self.get_status_from_instance_ref(instance_ref)

    def get_status_from_instance_ref(self, instance_ref):
        """Uses a compute instance ref to grab the instance status."""
        id = instance_ref['id']
        power_state = instance_ref['power_state']
        vm_state = instance_ref['vm_state']
        status = common.status_from_state(vm_state, power_state)
        return self.get_status_from_server_details(id, status)

    def get_status_from_server(self, server):
        # We're expecting the server dictionary as returned by the servers API.
        id = server['id']
        status = server['status']
        return self.get_status_from_server_details(id, status)

    def get_status_from_server_details(self, server_id, server_status):
        """
        Given a server id and its string status (the same as returned from the
        servers API) returns an Reddwarf InstanceStatus.

        Raises an exception if the server_id was not in the list of IDs used to
        originally create this InstanceStatusLookup.
        """
        if server_id not in self.local_ids:
            raise NotFound(message="Instance %s could not be found." % server_id)
        guest_status = self.guest_status_mapping.get(server_id)
        guest_state = None
        if guest_status is not None:
                guest_state = guest_status.state
        return InstanceStatus(guest_state=guest_state,
                              guest_status_debug_info=guest_status,
                              server_status=server_status)
