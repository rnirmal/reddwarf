# vim: tabstop=4 shiftwidth=4 softtabstop=4

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

import nova.api.openstack.views.versions

from nova.api.openstack import wsgi
from reddwarf.api import common


VERSIONS = {
    "v1.0": {
        "id": "v1.0",
        "status": "CURRENT",
        "updated": "2012-01-01T00:00:00Z",
        "links": [
        ],
    },
}

class Controller(object):
    """Supported versions"""

    def __init__(self):
        super(Controller, self).__init__()

    def dispatch(self, req, *args):
        """Respond to a request for all Reddwarf API versions."""
        builder = nova.api.openstack.views.versions.get_view_builder(req)
        if req.path in ('/', ''):
            return builder.build_versions(VERSIONS)
        else:
            return builder.build_version(VERSIONS['v1.0'])


def create_resource(version='1.0'):
    controller = {
        '1.0': Controller,
    }[version]()

    metadata = {
        'attributes': {
            'version': ['id', 'status', 'updated'],
            'link': ['rel', 'href', 'type'],
        }
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
