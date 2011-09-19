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
from nova import flags
from nova import log as logging
from sqlalchemy.sql import func
from sqlalchemy.sql import text
from sqlalchemy.orm.exc import NoResultFound
from nova.db.sqlalchemy.api import require_admin_context
from nova.db.sqlalchemy.models import Instance
from nova.db.sqlalchemy.models import Service
from nova.db.sqlalchemy.models import Volume
from nova.db.sqlalchemy.session import get_session
from nova.compute import power_state
from reddwarf.db import models

FLAGS = flags.FLAGS
LOG = logging.getLogger('reddwarf.db.api')

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
    :param session: pass in a active session if available
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

def guest_status_get_list(instance_ids, session=None):
    """Get the status of the given guests

    :param instance_ids: list of instance ids for the guests
    :param session: pass in a active session if available
    """
    if not session:
        session = get_session()
    result = session.query(models.GuestStatus).\
                         filter(models.GuestStatus.instance_id.in_(instance_ids)).\
                         filter_by(deleted=False)
    if not result:
        raise exception.InstanceNotFound(instance_id=instance_ids)
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

@require_admin_context
def show_instances_on_host(context, id):
    """Show all the instances that are on the given host id."""
    LOG.debug("show_instances_on_host id = %s" % str(id))
    session = get_session()
    with session.begin():
        count = session.query(Service).\
                        filter_by(host=id).\
                        filter_by(deleted=False).\
                        filter_by(disabled=False).count()
        if not count:
            raise exception.HostNotFound(host=id)
        result = session.query(Instance).\
                        filter_by(host=id).\
                        filter_by(deleted=False).all()
    return result


@require_admin_context
def instance_get_by_state_and_updated_before(context, state, time):
    """Finds instances in a specific state updated before some time."""
    session = get_session()
    result = session.query(Instance).\
                      filter_by(deleted=False).\
                      filter_by(state=state).\
                      filter(Instance.updated_at < time).\
                      all()
    if not result:
        return []
    return result


@require_admin_context
def instance_get_memory_sum_by_host(context, hostname):
    session = get_session()
    result = session.query(Instance).\
                      filter_by(host=hostname).\
                      filter_by(deleted=False).\
                      value(func.sum(Instance.memory_mb))
    if not result:
        return 0
    return result

@require_admin_context
def show_instances_by_account(context, id):
    """Show all the instances that are on the given account id."""
    LOG.debug("show_instances_by_account id = %s" % str(id))
    # This is the management API, so we want all the instances,
    # regardless of status.
    session = get_session()
    with session.begin():
        return session.query(Instance).\
                        filter_by(user_id=id).\
                        filter_by(deleted=False).\
                        order_by(Instance.host).all()
    raise exception.UserNotFound(user_id=id)


@require_admin_context
def volume_get_by_state_and_updated_before(context, state, time):
    """Finds instances in a specific state updated before some time."""
    session = get_session()
    result = session.query(Instance).\
                      filter_by(deleted=False).\
                      filter_by(state=state).\
                      filter(Instance.updated_at < time).\
                      all()
    if not result:
        return []
    return result

@require_admin_context
def volume_get_orphans(context, latest_time):
    session = get_session()
    result = session.query(Volume).\
                     filter_by(deleted=False).\
                     filter_by(instance_id=None).\
                     filter(Volume.status=='available').\
                     filter(Volume.updated_at < latest_time).\
                     all()                     
    return result

def get_root_enabled_timestamp(context, id):
    """
    Returns the timestamp recorded when root was first enabled for the
    given instance.
    """
    LOG.debug("Get root enabled timestamp for instance %s" % id)
    session = get_session()
    try:
        result = session.query(models.RootEnabledHistory).\
                     filter_by(instance_id=id).one()
    except NoResultFound:
        LOG.debug("No root enabled timestamp found for instance %s." % id)
        return None
    LOG.debug("Found root enabled timestamp for instance %s: %s"
              % (id, result.root_enabled_at))
    return result

def record_root_enabled_timestamp(context, id):
    """
    Records the current time in nova.root_enabled_history so admins can see
    when and if root was ever enabled for a database on an instance.
    """
    LOG.debug("Record root enabled timestamp for instance %s" % id)
    old_record = get_root_enabled_timestamp(context, id)
    if old_record is not None:
        LOG.debug("Found existing root enabled timestamp: %s %s" %
                  (old_record.instance_id, old_record.root_enabled_at))
        return old_record
    LOG.debug("Creating new root enabled timestamp.")
    new_record = models.RootEnabledHistory()
    new_record.update({'instance_id': id, 'root_enabled_at': datetime.datetime.utcnow()})
    session = get_session()
    with session.begin():
        new_record.save()
    LOG.debug("New root enabled timestamp: %s" % new_record)
    return new_record