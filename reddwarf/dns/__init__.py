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

from nova import flags

flags.DEFINE_string('dns_driver', 'reddwarf.dns.driver.DnsDriver',
                    'Driver to use for DNS work')
flags.DEFINE_string('dns_bridge_name', 'br100',
                    'Network bridge whose fixed_ip gets a DNS entry.')
flags.DEFINE_string('dns_instance_entry_factory',
                    'reddwarf.dns.driver.DnsInstanceEntryFactory',
                    'Method used to create entries for instances')
