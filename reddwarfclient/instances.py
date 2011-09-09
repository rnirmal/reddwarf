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


class Instance(base.Resource):
    """
    A Instance is an opaque instance used to store Database instances.
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
        self._delete("/instances/%s" % base.getid(instance))
