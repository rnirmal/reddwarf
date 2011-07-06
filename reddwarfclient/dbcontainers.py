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


class DbContainer(base.Resource):
    """
    A DbContainer is an opaque container used to store Database instances.
    """
    def __repr__(self):
        return "<DbContainer: %s>" % self.name

    def list_databases(self):
        return self.manager.databases.list(self)

    def delete(self):
        """
        Delete the container.
        """
        self.manager.delete(self)


class DbContainers(base.ManagerWithFind):
    """
    Manage :class:`DbContainer` resources.
    """
    resource_class = DbContainer

    def create(self, name, flavor_id, databases=None, volume=None):
        """
        Create (boot) a new dbcontainer.
        """
        body = {"dbcontainer": {
            "name": name,
            "flavorRef": flavor_id
        }}
        if databases:
            body["dbcontainer"]["databases"] = databases
        if volume:
            body["dbcontainer"]["volume"] = volume

        return self._create("/dbcontainers", body, "dbcontainer")

    def _list(self, url, response_key):
        resp, body = self.api.client.get(url)
        if not body:
            raise Exception("Call to " + url + " did not return a body.")
        return [self.resource_class(self, res) for res in body[response_key]]

    def list(self):
        """
        Get a list of all dbcontainers.

        :rtype: list of :class:`DbContainer`.
        """
        return self._list("/dbcontainers/detail", "dbcontainers")

    def index(self):
        """
        Get a list of all dbcontainers.

        :rtype: list of :class:`DbContainer`.
        """
        return self._list("/dbcontainers", "dbcontainers")

    def details(self):
        """
        Get details of all dbcontainers.

        :rtype: list of :class:`DbContainer`.
        """
        return self._list("/dbcontainers/detail", "dbcontainers")

    def get(self, dbcontainer):
        """
        Get a specific containers.

        :rtype: :class:`DbContainer`
        """
        return self._get("/dbcontainers/%s" % base.getid(dbcontainer),
                        "dbcontainer")

    def delete(self, dbcontainer):
        """
        Delete the specified container.

        :param dbcontainer_id: The container id to delete
        """
        self._delete("/dbcontainers/%s" % base.getid(dbcontainer))
