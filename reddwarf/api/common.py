# Copyright 2010 OpenStack LLC.
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
Common shared code across DBaaS API
"""

from nova import exception as nova_exception
from nova import log as logging
from nova.compute import power_state
from nova.db.sqlalchemy.api import is_admin_context

from reddwarf import exception
from reddwarf.db import api as dbapi
from reddwarf.guest.db import models


XML_NS_V10 = 'http://docs.openstack.org/database/api/v1.0'
LOG = logging.getLogger('reddwarf.api.common')

dbaas_mapping = {
    None: 'BUILD',
    power_state.NOSTATE: 'BUILD',
    power_state.RUNNING: 'ACTIVE',
    power_state.SHUTDOWN: 'SHUTDOWN',
    power_state.BUILDING: 'BUILD',
    power_state.FAILED: 'FAILED',

    power_state.BLOCKED: 'BLOCKED',
    power_state.PAUSED: 'SHUTDOWN',
    power_state.SHUTOFF: 'SHUTDOWN',
    power_state.CRASHED: 'SHUTDOWN',
    power_state.SUSPENDED: 'FAILED',
}


def populate_databases(dbs):
    """
    Create a serializable request with user provided data
    for creating new databases.
    """
    try:
        databases = []
        for database in dbs:
            mydb = models.MySQLDatabase()
            mydb.name = database.get('name', '')
            mydb.character_set = database.get('character_set', '')
            mydb.collate = database.get('collate', '')
            databases.append(mydb.serialize())
        return databases
    except ValueError as ve:
        raise exception.BadRequest(ve.message)


def populate_users(users):
    """Create a serializable request containing users"""
    try:
        users_data = []
        for user in users:
            u = models.MySQLUser()
            u.name = user.get('name', '')
            u.password = user.get('password', '')
            dbs = user.get('databases', '')
            if dbs:
                for db in dbs:
                    u.databases = db.get('name', '')
            users_data.append(u.serialize())
        return users_data
    except ValueError as ve:
        raise exception.BadRequest(ve.message)


def instance_exists(ctxt, id, compute_api):
    """Verify the instance exists before issuing any other call"""
    try:
        return compute_api.get(ctxt, id)
    except nova_exception.NotFound:
        raise exception.NotFound()

def instance_available(ctxt, instance_id, local_id, compute_api):
    """ Verify the instance is available"""
    instance_exists(ctxt, instance_id, compute_api)
    running = power_state.RUNNING
    status = dbapi.guest_status_get(local_id).state
    if status != running:
        msg = "Instance %s is not currently available." % instance_id
        LOG.debug(msg)
        raise exception.UnprocessableEntity(msg)

def verify_admin_context(f):
    """
    Verify that the current context has administrative access,
    or throw an exception. Reddwarf API functions typically take the form
    function(self, req), or function(self, req, id).
    """
    def wrapper(*args, **kwargs):
        if not 'req' in kwargs:
          raise nova_exception.Error("Need a reddwarf request to extract the context.")
        req = kwargs['req']
        if not hasattr(req, 'environ'):
          raise nova_exception.Error("Request needs an environment to extract the context.")
        context = req.environ.get('nova.context', None)
        if context is None:
          raise nova_exception.Error("Request context is None; cannot verify admin access.")
        if not is_admin_context(context):
            raise exception.Unauthorized("User does not have admin privileges.")
        return f(*args, **kwargs)
    return wrapper
