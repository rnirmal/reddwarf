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
Dns manager.
"""

from nova import flags
from nova import utils
from nova.manager import Manager

FLAGS = flags.FLAGS
flags.DEFINE_string('dns_driver', 'nova.dns.driver.DnsDriver',
                    'Driver to use for DNS work')
flags.DEFINE_string('dns_instance_entry_mapper',
                    'nova.dns.driver.DnsInstanceEntryCreator',
                    'Method used to create entries for instances')


class DnsManager(Manager):
    """Handles associating DNS to and from IPs."""

    def __init__(self, dns_driver=None, dns_instance_entry_mapper=None,
                 *args, **kwargs):
        if not dns_driver:
            dns_driver = FLAGS.dns_driver
        self.driver = utils.import_object(dns_driver)
        if not dns_instance_entry_mapper:
            dns_instance_entry_mapper = FLAGS.dns_instance_entry_mapper
        self.entry_factory = utils.import_object(dns_instance_entry_mapper)
        super(DnsManager, self).__init__(*args, **kwargs)

    def create_instance_entry(self, instance, address):
        """Connects a new instance with a DNS entry.

        :param instance: The compute instance to associate.
        :param address: The IP address attached to the instance.

        """
        entry = self.entry_factory.create_entry(instance)
        if entry:
            entry.address = address
            self.driver.create_entry(entry)

    def delete_instance_entry(self, instance, address):
        """Removes a DNS entry associated to an instance."""
        entry = self.entry_factory.create_entry(instance)
        if entry:
            entry.address = address
            self.driver.delete_entry(entry.name)
