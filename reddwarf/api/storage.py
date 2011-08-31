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

from nova import flags
from nova import rpc
from nova import log as logging
from nova.api.openstack import wsgi
from reddwarf.api import common

LOG = logging.getLogger('reddwarf.api.storage')
LOG.setLevel(logging.DEBUG)


FLAGS = flags.FLAGS


class Controller(object):
    """ The Storage Management Controller for the Platform API """

    def __init__(self):
        super(Controller, self).__init__()

    def index(self, req):
        """List all the storage devices in the system"""
        LOG.info("List all the storage devices in the system")
        LOG.debug("%s - %s", req.environ, req.body)
        ctxt = req.environ['nova.context']
        storage_info = rpc.call(ctxt,
                                 FLAGS.volume_topic,
                                 {"method": "get_storage_device_info",
                                  "args": {}})
        return {'storage': { 'name': storage_info['name'],
                             'type': storage_info['type'],
                             'availablesize': storage_info['prov_avail'],
                             'totalsize': storage_info['prov_total']}}


def create_resource(version='1.0'):
    controller = {
        '1.0': Controller,
    }[version]()

    metadata = {
        "attributes": {
            "device": ["id", "name", "type", "availablesize", "totalsize"],
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
