# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright (c) 2011 Openstack, LLC.
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
Dns Driver base class that all Schedulers should inherit from
"""


from nova.exception import NotFound


class DnsDriver(object):
    """The base class that all Dns drivers should inherit from."""

    def __init__(self):
        pass

    def create_entry(self, entry):
        pass

    def delete_entry(self, name, dns_zone=""):
        pass

    def delete_instance_entry(self, instance, address):
        pass

    def get_entries_by_address(self, address, dns_zone=""):
        pass

    def get_entries_by_name(self, name, dns_zone=""):
        pass

    def get_dns_zones(self):
        pass

    def modify_address(self, name, address, dns_zone):
        pass

    def rename_entry(self, address, name, dns_zone):
        pass


class DnsInstanceEntryCreator(object):
    """Defines how instance DNS entries are created for instances.

    By default, the DNS entry returns None meaning instances do not get entries
    associated with them. Override the create_entry method to change this
    behavior.

    """

    def create_entry(self, instance):
        return None


class DnsSimpleInstanceEntryCreator(object):
    """Creates a CNAME with the name being the instance name."""

    def create_entry(self, instance):
        return DnsEntry(name=instance.name, address=None, type="CNAME")


class DnsEntry(object):
    """Simple representation of a DNS record.

    http://en.wikipedia.org/wiki/Domain_Name_System
    RR (Resource record) fields

    """

    #TODO(tim.simpson) "content" & "data" seem more widely used than "address."
    def __init__(self, name, address, type, priority=None, dns_zone=""):
        self.address = address
        self.name = name
        self.type = type
        self.priority = priority
        self.dns_zone = dns_zone


class DnsEntryNotFound(NotFound):
    """Raised when a driver cannot find a DnsEntry."""
    pass