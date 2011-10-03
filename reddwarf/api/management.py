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

from webob import exc

from nova import compute
from nova import flags
from nova import log as logging
from nova import utils
from nova import volume
from nova.api.openstack import servers
from nova.api.openstack import wsgi
from nova.compute import power_state
from nova.exception import InstanceNotFound
from nova.guest import api as guest

from reddwarf.api import common
from reddwarf.api.views import instances
from reddwarf.db import api as dbapi

LOG = logging.getLogger('reddwarf.api.management')
LOG.setLevel(logging.DEBUG)


FLAGS = flags.FLAGS

def create_resource(version='1.0'):
    controller = {
        '1.0': Controller,
    }[version]()

    metadata = {
        'application/xml': {
            'attributes': {
                'instance': ['account_id',
                             'flavor',
                             'host',
                             'id',
                             'name',
                             'root_enabled_at',
                             'root_enabled_by',
                             'server_state_description'],
                'guest_status': ['created_at',
                           'deleted',
                           'deleted_at',
                           'instance_id',
                           'state',
                           'state_description',
                           'updated_at'],
                'link': ['rel',
                         'type',
                         'href'],
                'database': ['name',
                             'collate',
                             'character_set'],
                'user': ['name'],
                'volume': [ 'id',
                            'size',
                            'description',
                            'name'],
                'root_enabled_history': [ 'id',
                                          'root_enabled_at',
                                          'root_enabled_by'],
            },
        },

    }

    xmlns = {
        '1.0': common.XML_NS_V10,
    }[version]

    serializers = {
        'application/xml': wsgi.XMLDictSerializer(metadata=metadata,
                                                  xmlns=xmlns),
    }

    response_serializer = wsgi.ResponseSerializer(body_serializers=serializers)
    return wsgi.Resource(controller, serializer=response_serializer)


class Controller(object):
    """ The Instance API controller for the Management API """

    def __init__(self):
        self.compute_api = compute.API()
        self.dns_entry_factory = \
            utils.import_object(FLAGS.dns_instance_entry_factory)
        self.server_controller = servers.ControllerV11()
        self.volume_api = volume.API()
        self.guest_api = guest.API()
        self.instance_view = instances.MgmtViewBuilder()
        super(Controller, self).__init__()

    def show(self, req, id):
        """ Returns instance details by instance id """
        LOG.info("Get Instance Detail by ID - %s", id)
        LOG.debug("%s - %s", req.environ, req.body)
        context = req.environ['nova.context']

        # Let's make sure the instance exists first.
        # If it doesn't, we'll get an exception.
        try:
            status = dbapi.guest_status_get(id)
        except InstanceNotFound:
            #raise InstanceNotFound(instance_id=id)
            raise exc.HTTPNotFound("No instance with id %s." % id)

        server = self.server_controller.show(req, id)['server']
        if isinstance(server, Exception):
            # The server controller has a habit of returning exceptions
            # instead of raising them.
            return server

        # Use the compute api response to add additional information
        instance_ref = self.compute_api.get(context, id)
        LOG.debug("Instance Info from Compute API : %r" % instance_ref)

        guest_state = {server['id']: status.state}
        instance = self.instance_view.build_mgmt_single(server, instance_ref,
                                                        req.application_url,
                                                        guest_state)
        instance = self._get_guest_info(context, id, status, instance)
        return {'instance': instance}

    def _get_guest_info(self, context, id, status, instance):
        """Get all the guest details and add it to the response"""
        if status.state != power_state.RUNNING:
            dbs = None
            users = None
        else:
            db_list = self.guest_api.list_databases(context, id)

            LOG.debug("DBS: %r" % db_list)
            dbs = [{
                    'name': db['_name'],
                    'collate': db['_collate'],
                    'character_set': db['_character_set']
                    } for db in db_list]
            users = self.guest_api.list_users(context, id)
            users = [{'name': user['_name']} for user in users]

        root_access = dbapi.get_root_enabled_history(context, id)

        instance = self.instance_view.build_guest_info(instance, status=status,
                                                       dbs=dbs, users=users,
                                                       root_enabled=root_access)
        return instance

    def root_enabled_history(self, req, id):
        """ Checks the root_enabled_history table to see if root access
            was ever enabled for this instance, and if so, when and by who. """
        LOG.info("Call to root_enabled_history for instance %s", id)
        LOG.debug("%s - %s", req.environ, req.body)
        ctxt = req.environ['nova.context']
        common.instance_exists(ctxt, id, self.compute_api)
        try:
            result = dbapi.get_root_enabled_history(ctxt, id)
            root_history = self.instance_view.build_root_history(id, result)
            return {'root_enabled_history': root_history}
        except Exception as err:
            LOG.error(err)
            return exc.HTTPError("Error determining root access history")
