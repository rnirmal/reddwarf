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

"""
dnsclient module.
"""

__version__ = '2.4'

from rsdns.client.dns_client import DNSaasClient
from rsdns.client.domains import DomainsManager
from rsdns.client.records import RecordsManager


class DNSaas(object):
    """
    Top-level object to access the DNSaas service
    """

    def __init__(self, accountId, username, apikey,
                 auth_url='https://auth.api.rackspacecloud.com/v1.0',
                 management_base_url=None):
        self.client = DNSaasClient(accountId, username, apikey, auth_url,
                                   management_base_url)
        self.domains = DomainsManager(self)
        self.records = RecordsManager(self)

    def authenticate(self):
        """
        Authenticate against the server.

        Normally this is called automatically when you first access the API,
        but you can call this method to force authentication right now.

        Returns on success; raises :exc:`novaclient.Unauthorized` if the
        credentials are wrong.
        """
        self.client.authenticate()

