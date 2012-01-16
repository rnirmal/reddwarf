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

from nova import exception as nova_exception
from nova import flags
from nova import log as logging
from nova.api.openstack import wsgi
from nova.db.sqlalchemy.api import service_get_all_compute_sorted

from reddwarf import exception
from reddwarf.api import common
from reddwarf.db import api as dbapi
from reddwarf.scheduler import simple # import used for FLAG values

LOG = logging.getLogger('reddwarf.api.hosts')
LOG.setLevel(logging.DEBUG)


FLAGS = flags.FLAGS


class Controller(object):
    """ The Host Management Controller for the Platform API """

    def __init__(self):
        super(Controller, self).__init__()

    @common.verify_admin_context
    def index(self, req):
        """List all the hosts on the system"""
        LOG.info("List all the nova-compute hosts in the system")
        LOG.debug("%s - %s", req.environ, req.body)
        ctxt = req.environ['nova.context']
        services = service_get_all_compute_sorted(ctxt)
        # services looks like (Service(object), Decimal('0'))
        # must convert from Decimal('0') to int() because no JSON repr
        hosts = [{'name':srv[0].host,
                  'instanceCount':int(srv[1])}
                  for srv in services]
        return {'hosts': hosts}

    #TODO(cp16net): this would be nice to use if zones are working for us
    #@check_host
    @common.verify_admin_context
    def show(self, req, id):
        """List all the instances on the host given"""
        try:
            LOG.info("List the info on nova-compute '%s'" % id)
            LOG.debug("%s - %s", req.environ, req.body)
            ctxt = req.environ['nova.context']
            instances = dbapi.show_instances_on_host(ctxt, id)
            instances = [{'id': c.id,
                          'name': c.display_description,
                          'status': c.vm_state} for c in instances]
            total_ram = FLAGS.max_instance_memory_mb
            used_ram = dbapi.instance_get_memory_sum_by_host(ctxt, id)
            percent = int(round((used_ram / total_ram) * 100))
            return {'host': {'name': id,
                             'percentUsed': percent,
                             'totalRAM': total_ram,
                             'usedRAM': int(used_ram),
                             'instances': instances}}
        except nova_exception.HostNotFound:
            raise exception.NotFound()


def create_resource(version='1.0'):
    controller = {
        '1.0': Controller,
    }[version]()

    metadata = {
        'attributes': {
            'host': ['name', 'instanceCount', 'percentUsed',
                     'totalRAM', 'usedRAM'],
            'instance': ['id', 'name', 'status'],
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
