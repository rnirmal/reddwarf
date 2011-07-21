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
from nova import log as logging
from nova.api.openstack import wsgi
from nova.api.platform.dbaas import common
from nova.db.sqlalchemy.api import service_get_all_compute_sorted
from reddwarf.db.api import show_containers_on_host

LOG = logging.getLogger('nova.api.platform.dbaas.hosts')
LOG.setLevel(logging.DEBUG)


FLAGS = flags.FLAGS


class Controller(object):
    """ The Host Management Controller for the Platform API """

    def __init__(self):
        super(Controller, self).__init__()

    def index(self, req):
        """List all the hosts on the system"""
        LOG.info("List all the nova-compute hosts in the system")
        LOG.debug("%s - %s", req.environ, req.body)
        ctxt = req.environ['nova.context']
        services = service_get_all_compute_sorted(ctxt)
        hosts = [{'name':srv[0].host,
                  'instanceCount':str(srv[1])}
                  for srv in services]
        return {'hosts': hosts}

    #TODO(cp16net): this would be nice to use if zones are working for us
    #@check_host
    def show(self, req, id):
        """List all the dbcontainers on the host given"""
        LOG.info("List all the nova-compute hosts in the system")
        LOG.debug("%s - %s", req.environ, req.body)
        ctxt = req.environ['nova.context']
        containers = show_containers_on_host(ctxt,id)
        dbcontainers = [{'id':c.id} for c in containers]
        return {'host': {'name':id, 'dbcontainers':dbcontainers}}

def create_resource(version='1.0'):
    controller = {
        '1.0': Controller,
    }[version]()

    metadata = {
        "attributes": {
            "host": ["name","instanceCount"],
            "dbcontainer": ["id"],
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
