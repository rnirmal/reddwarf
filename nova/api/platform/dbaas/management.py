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
from nova import db
from nova import exception
from nova import flags
from nova import log as logging
from nova import utils
from nova import volume
from nova.api.openstack import flavors
from nova.api.openstack import servers
from nova.api.openstack import wsgi
from nova.api.platform.dbaas import common
from nova.exception import InstanceNotFound
from nova.guest import api as guest
from nova.utils import poll_until
from reddwarf.db import api as dbapi

LOG = logging.getLogger('nova.api.platform.dbaas.management')
LOG.setLevel(logging.DEBUG)


FLAGS = flags.FLAGS

def create_resource(version='1.0'):
    controller = {
        '1.0': Controller,
    }[version]()

    metadata = {
        'application/xml': {
            'attributes': {
                'dbcontainer': ['account_id', 'flavorRef', 'host', 'id', 'name'],
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
        self.server_controller = servers.ControllerV11()
        self.volume_api = volume.API()
        self.guest_api = guest.API()
        super(Controller, self).__init__()

    def show(self, req, id):
        """ Returns dbcontainer details by container id """
        LOG.info("Get Instance Detail by ID - %s", id)
        LOG.debug("%s - %s", req.environ, req.body)
        context = req.environ['nova.context']

        instance = self.compute_api.get(context, id)
        if isinstance(instance, Exception):
            return instance

        dbs = self.guest_api.list_databases(context, id)
        if isinstance(dbs, Exception):
            return dbs

        LOG.debug("DBS: %r" % dbs)
        dbs = [{
                'name': db['_name'],
                'collate': db['_collate'],
                'character_set': db['_character_set']
                } for db in dbs]

        users = self.guest_api.list_users(context, id)
        if isinstance(users, Exception):
            return users
        users = [{'name': user['_name']} for user in users]

        volume = self.volume_api.get(context, id)
        if isinstance(volume, Exception):
            return volume
        volume = {
            'id': volume['id'],
            'name': volume['display_name'],
            'size': volume['size'],
            'description': volume['display_description'],
            }

        server = self.server_controller.show(req, id)
        if isinstance(server, Exception):
            return server
        flavorRef = server['server']['flavorRef']
        
        resp = {
            'dbcontainer': {
                'id': id,
                'name': instance['display_name'],
                'host': instance['host'],
                'account_id': instance['user_id'],
                'flavorRef': flavorRef,
                'databases': dbs,
                'users': users,
                'volume': volume,
            },
        }
        return resp
