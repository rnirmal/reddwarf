# Copyright 2011 OpenStack LLC.
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
from nova.api.openstack import wsgi

from reddwarf.db import api as dbapi
from reddwarf.api import common
from reddwarf.guest import api

LOG = logging.getLogger('reddwarf.api.guests')
LOG.setLevel(logging.DEBUG)


FLAGS = flags.FLAGS


class Controller(object):
    """ The Guest Management Controller for the Platform API """

    def __init__(self):
        self.guest_api = api.API()
        self.compute_api = compute.API()
        super(Controller, self).__init__()

    @common.verify_admin_context
    def upgrade(self, req, id):
        """Upgrade the guest for a specific instance"""
        LOG.info("Upgrade of nova-guest issued for instance : %s", id)
        LOG.debug("%s - %s", req.environ, req.body)
        local_id = dbapi.localid_from_uuid(id)
        ctxt = req.environ['nova.context']
        common.instance_exists(ctxt, id, self.compute_api)

        self.guest_api.upgrade(ctxt, local_id)
        return exc.HTTPAccepted()

    @common.verify_admin_context
    def upgradeall(self, req):
        """Upgrade the guests for all the instances"""
        LOG.info("Upgrade all nova-guest issued")
        LOG.debug("%s - %s", req.environ, req.body)
        ctxt = req.environ['nova.context']
        #TODO(rnirmal): Convert to using fanout once Nova code is merged in
        instances = self.compute_api.get_all(ctxt)
        for instance in instances:
            self.guest_api.upgrade(ctxt, str(instance['id']))
        return exc.HTTPAccepted()


def create_resource(version='1.0'):
    controller = {
        '1.0': Controller,
    }[version]()

    metadata = {
        "attributes": {
        },
    }

    xmlns = {
        '1.0': common.XML_NS_V10,
    }[version]

    serializers = {
        'application/xml': wsgi.XMLDictSerializer(metadata=metadata,
                                                  xmlns=xmlns),
    }

    deserializers = {
        'application/xml': wsgi.TextDeserializer(),
        'application/json': wsgi.TextDeserializer(),
    }

    response_serializer = wsgi.ResponseSerializer(body_serializers=serializers)
    request_deserializer = wsgi.RequestDeserializer(deserializers)
    return wsgi.Resource(controller, deserializer=request_deserializer,
                         serializer=response_serializer)
