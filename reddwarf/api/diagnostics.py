# Copyright 2012 OpenStack LLC.
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

from nova import compute
from nova import log as logging
from nova.api.openstack import wsgi

from reddwarf import exception
from reddwarf.api import common
from reddwarf.db import api as dbapi
from reddwarf.guest import api as guest_api

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)


class Controller(object):
    """ Get some diagnostics of the guest. """

    def __init__(self):
        self.guest_api = guest_api.API()
        self.compute_api = compute.API()
        super(Controller, self).__init__()

    @common.verify_admin_context
    def get_diagnostics(self, req, id):
        """ Returns the diagnostics of the guest on the instance. """
        LOG.info("Call to getDiagnostics for instance %s", id)
        LOG.debug("%s - %s", req.environ, req.body)
        local_id = dbapi.localid_from_uuid(id)
        ctxt = req.environ['nova.context']
        common.instance_available(ctxt, id, local_id, self.compute_api)
        try:
            diags = self.guest_api.get_diagnostics(ctxt, local_id)
            LOG.debug("get_diagnostics: %r" % diags)
            ret_diags = {}
            ret_diags['version'] = diags['version']
            ret_diags['threads'] = diags['threads']
            ret_diags['fdSize'] = diags['fd_size']
            ret_diags['vmSize'] = diags['vm_size']
            ret_diags['vmPeak'] = diags['vm_peak']
            ret_diags['vmRss'] = diags['vm_rss']
            ret_diags['vmHwm'] = diags['vm_hwm']
            return {"diagnostics":ret_diags}
        except Exception as err:
            LOG.error(err)
            raise exception.InstanceFault("Error determining diagnostics")

def create_resource(version='1.0'):
    controller = {
        '1.0': Controller,
    }[version]()

    metadata = {
        "attributes": {
            'diagnostics': ['version',
                            'fdSize',
                            'vmSize',
                            'vmPeak',
                            'vmRss',
                            'vmHwm',
                            'threads']
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
