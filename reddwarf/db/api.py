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
API Interface for reddwarf datastore operations
"""

import datetime

from nova import exception
from nova.db.sqlalchemy.session import get_session
from nova.compute import power_state
from reddwarf.db import models


def guest_status_create(instance_id):
    """Create a new guest status for the instance

    :param instance_id: instance id for the guest
    """
    guest_status = models.GuestStatus()
    state = power_state.BUILDING
    guest_status.update({'instance_id': instance_id,
                         'state': state,
                         'state_description': power_state.name(state)})

    session = get_session()
    with session.begin():
        guest_status.save(session=session)
    return guest_status


def guest_status_get(instance_id, session=None):
    """Get the status of the guest

    :param instance_id: instance id for the guest
    "param session: pass in a active session if available
    """
    if not session:
        session = get_session()
    result = session.query(models.GuestStatus).\
                         filter_by(instance_id=instance_id).\
                         filter_by(deleted=False).\
                         first()
    if not result:
        raise exception.InstanceNotFound(instance_id=instance_id)
    return result


def guest_status_update(instance_id, state, description=None):
    """Update the state of the guest with one of the valid states
       along with the description

    :param instance_id: instance id for the guest
    :param state: state id
    :param description: description of the state
    """
    if not description:
        description = power_state.name(state)

    session = get_session()
    with session.begin():
        session.query(models.GuestStatus).\
                filter_by(instance_id=instance_id).\
                update({'state': state,
                        'state_description': description})


def guest_status_delete(instance_id):
    """Set the specified instance state as deleted

    :param instance_id: instance id for the guest
    """
    state = power_state.SHUTDOWN
    session = get_session()
    with session.begin():
        session.query(models.GuestStatus).\
                filter_by(instance_id=instance_id).\
                update({'deleted': True,
                        'deleted_at': datetime.datetime.utcnow(),
                        'state': state,
                        'state_description': power_state.name(state)})
