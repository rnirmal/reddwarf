# vim: tabstop=4 shiftwidth=4 softtabstop=4

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

from nova import log as logging
from nova.api.openstack import images as nova_images
from nova.api.openstack import wsgi
from reddwarf.api import common
from reddwarf.api import views


LOG = logging.getLogger('reddwarf.api.imagess')
LOG.setLevel(logging.DEBUG)

class Controller(nova_images.ControllerV11):
    @common.verify_admin_context
    def create(self, req, body):
        return super(Controller, self).create(req, body)

    @common.verify_admin_context
    def delete(self, req, id):
        return super(Controller, self).delete(req, id)

    @common.verify_admin_context
    def detail(self, req):
        return super(Controller, self).detail(req)

    @common.verify_admin_context
    def index(self, req):
        return super(Controller, self).index(req)

    @common.verify_admin_context
    def show(self, req, id):
        return super(Controller, self).show(req, id)

def create_resource():
    controller = Controller()
    metadata = {
        "attributes": {
            "image": ["id", "name", "updated", "created", "status",
                      "serverId", "progress", "serverRef"],
            "link": ["rel", "type", "href"],
        },
    }

    xml_serializer = wsgi.XMLDictSerializer(metadata, wsgi.XMLNS_V10)
    body_serializers = { 'application/xml': xml_serializer }
    serializer = wsgi.ResponseSerializer(body_serializers)
    return wsgi.Resource(controller, serializer=serializer)
    
