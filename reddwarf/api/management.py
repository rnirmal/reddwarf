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
from reddwarf.api import common
from nova.compute import power_state
from nova.exception import InstanceNotFound, InstanceNotRunning
from nova.guest import api as guest
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
                'dbcontainer': ['account_id', 'flavor', 'host', 'id', 'name'],
                'link': ['rel', 'type', 'href'],
                'database': ['name', 'collate', 'character_set'],
                'user': ['name'],
                'volume': [ 'id', 'size', 'description', 'name']
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
    """ The DBContainer API controller for the Management API """

    def __init__(self):
        self.compute_api = compute.API()
        self.dns_entry_factory = \
            utils.import_object(FLAGS.dns_instance_entry_factory)
        self.server_controller = servers.ControllerV11()
        self.volume_api = volume.API()
        self.guest_api = guest.API()
        super(Controller, self).__init__()

    def show(self, req, id):
        """ Returns dbcontainer details by container id """
        LOG.info("Get Instance Detail by ID - %s", id)
        LOG.debug("%s - %s", req.environ, req.body)
        context = req.environ['nova.context']

        # Let's make sure the container exists first.
        # If it doesn't, we'll get an exception.
        try:
            status = dbapi.guest_status_get(id)
        except InstanceNotFound:
            #raise InstanceNotFound(instance_id=id)
            raise exc.HTTPNotFound("No container with id %s." % id)
        if status.state != power_state.RUNNING:
            raise InstanceNotRunning(instance_id=id)

        instance = self.compute_api.get(context, id)

        db_list = self.guest_api.list_databases(context, id)

        LOG.debug("DBS: %r" % db_list)
        dbs = [{
                'name': db['_name'],
                'collate': db['_collate'],
                'character_set': db['_character_set']
                } for db in db_list]

        users = self.guest_api.list_users(context, id)
        users = [{'name': user['_name']} for user in users]

        volume = instance['volumes'][0]
        volume = {
            'id': volume['id'],
            'name': volume['display_name'],
            'size': volume['size'],
            'description': volume['display_description'],
            }

        server = self.server_controller.show(req, id)
        if isinstance(server, Exception):
            # The server controller has a habit of returning exceptions
            # instead of raising them.
            return server
        flavorRef = server['server']['flavor']['id']
        addresses = server['server']['addresses']

        resp = {
            'dbcontainer': {
                'id': id,
                'name': instance['display_name'],
                'host': instance['host'],
                'account_id': instance['user_id'],
                'flavor': flavorRef,
                'addresses': addresses,
                'databases': dbs,
                'users': users,
                'volume': volume,
            },
        }
        dns_entry = self.dns_entry_factory.create_entry(instance)
        if dns_entry:
            resp["dbcontainer"]["hostname"] = dns_entry.name
        return resp
