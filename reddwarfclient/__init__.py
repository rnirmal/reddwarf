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

from novaclient import OpenStack

from reddwarfclient.dbcontainers import DbContainers
from reddwarfclient.databases import Databases
from reddwarfclient.hosts import Hosts
from reddwarfclient.management import Management
from reddwarfclient.storage import StorageInfo
from reddwarfclient.users import Users
from reddwarfclient.root import Root

# To write this test from an end user perspective, we have to create a client
# similar to the CloudServers one.
# For now we will work on it here.

class Dbaas(OpenStack):
    """
    Top-level object to access the Rackspace Database as a Service API.

    Create an instance with your creds::

        >>> cs = Dbaas(USERNAME, API_KEY [, AUTH_URL])

    Then call methods on its managers::

        >>> cs.servers.list()
        ...
        >>> cs.flavors.list()
        ...

    &c.
    """

    def __init__(self, username, apikey,
                 auth_url='https://auth.api.rackspacecloud.com/v1.1'):
        OpenStack.__init__(self, username, apikey, auth_url)
        self.databases = Databases(self)
        self.dbcontainers = DbContainers(self)
        self.users = Users(self)
        self.root = Root(self)
        self.hosts = Hosts(self)
        self.storage = StorageInfo(self)
        self.management = Management(self)
