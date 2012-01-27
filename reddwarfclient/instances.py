# Copyright (c) 2011 OpenStack, LLC.
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

from novaclient import base

import exceptions

from reddwarfclient.common import check_for_exceptions


REBOOT_SOFT, REBOOT_HARD = 'SOFT', 'HARD'


class Instance(base.Resource):
    """
    An Instance is an opaque instance used to store Database instances.
    """
    def __repr__(self):
        return "<Instance: %s>" % self.name

    def list_databases(self):
        return self.manager.databases.list(self)

    def delete(self):
        """
        Delete the instance.
        """
        self.manager.delete(self)

    def reboot(self, type=REBOOT_SOFT):
        """
        Reboot the server.

        :param type: either :data:`REBOOT_SOFT` to restart MySQL, or
                     `REBOOT_HARD` to restart the underlying VM.
        """
        self.manager.reboot(self.id, type)


class Instances(base.ManagerWithFind):
    """
    Manage :class:`Instance` resources.
    """
    resource_class = Instance

    def create(self, name, flavor_id, volume, databases=None):
        """
        Create (boot) a new instance.
        """
        body = {"instance": {
            "name": name,
            "flavorRef": flavor_id,
            "volume": volume
        }}
        if databases:
            body["instance"]["databases"] = databases

        return self._create("/instances", body, "instance")

    def _list(self, url, response_key):
        resp, body = self.api.client.get(url)
        if not body:
            raise Exception("Call to " + url + " did not return a body.")
        return [self.resource_class(self, res) for res in body[response_key]]

    def list(self):
        """
        Get a list of all instances.

        :rtype: list of :class:`Instance`.
        """
        return self._list("/instances/detail", "instances")

    def index(self):
        """
        Get a list of all instances.

        :rtype: list of :class:`Instance`.
        """
        return self._list("/instances", "instances")

    def details(self):
        """
        Get details of all instances.

        :rtype: list of :class:`Instance`.
        """
        return self._list("/instances/detail", "instances")

    def get(self, instance):
        """
        Get a specific instances.

        :rtype: :class:`Instance`
        """
        return self._get("/instances/%s" % base.getid(instance),
                        "instance")

    def delete(self, instance):
        """
        Delete the specified instance.

        :param instance_id: The instance id to delete
        """
        resp, body = self.api.client.delete("/instances/%s" % base.getid(instance))
        if resp.status in (422, 500):
            raise exceptions.from_response(resp, body)

    def _action(self, instance_id, body):
        """
        Perform a server "action" -- reboot/rebuild/resize/etc.
        """
        url = "/instances/%s/action" % instance_id
        resp, body = self.api.client.post(url, body=body)
        check_for_exceptions(resp, body)

    def resize(self, instance_id, volume_size):
        """
        Resize the volume on an existing instances
        """
        body = {"resize": {"volume": {"size": volume_size}}}
        self._action(instance_id, body)

    def reboot(self, instance_id, type=REBOOT_SOFT):
        """
        Reboot a server.

        :param server: The :class:`Server` (or its ID) to share onto.
        :param type: either :data:`REBOOT_SOFT` for a software-level reboot,
                     or `REBOOT_HARD` for a virtual power cycle hard reboot.
        """
        body = {'reboot': {'type': type}}
        self._action(instance_id, body)
