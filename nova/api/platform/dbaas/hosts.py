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
from nova.api.platform.dbaas import common
from reddwarf.db import api as dbapi

LOG = logging.getLogger('nova.api.platform.dbaas.hosts')
LOG.setLevel(logging.DEBUG)


FLAGS = flags.FLAGS


class Controller(common.DBaaSController):
    """ The Host Management Controller for the Platform API """

    _serialization_metadata = {
        'application/xml': {
            "attributes": {
                "host": ["name","instanceCount"],
                "dbcontainer": ["id"],
            },
        },
    }

    def __init__(self):
        self.host_api = compute.API()
        super(Controller, self).__init__()

    def index(self, req):
        """List all the hosts on the system"""
        LOG.info("List all the nova-compute hosts in the system")
        LOG.debug("%s - %s", req.environ, req.body)
        ctxt = req.environ['nova.context']
        services = dbapi.list_compute_hosts(ctxt)
        resp = {'hosts':[]}
        for srv in services:
            resp['hosts'].append({'name':srv.Service.host,
                                  'instanceCount':srv.instance_count})
        return resp

    def show(self, req, id):
        """List all the dbcontainers on the host given"""
        LOG.info("List all the nova-compute hosts in the system")
        LOG.debug("%s - %s", req.environ, req.body)
        ctxt = req.environ['nova.context']
        containers = dbapi.show_containers_on_host(ctxt, id)
        resp = {'host': {'name':id, 'dbcontainers':[]}}
        for c in containers:
            resp['host']['dbcontainers'].append({'id':c.id})
        return resp
