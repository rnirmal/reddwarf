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


class User(base.Resource):
    """
    A database user
    """
    def __repr__(self):
        return "<User: %s>" % self.name


class Users(base.ManagerWithFind):
    """
    Manage :class:`Users` resources.
    """
    resource_class = User

    def create(self, dbcontainer_id, users):
        """
        Create users with permissions to the specified databases
        """
        body = {"users": users}
        url = "/dbcontainers/%s/users" % dbcontainer_id
        resp, body = self.api.client.post(url, body=body)

    def delete(self, dbcontainer_id, user):
        """Delete an existing user in the specified container"""
        url = "/dbcontainers/%s/users/%s"% (dbcontainer_id, user)
        self._delete(url)
