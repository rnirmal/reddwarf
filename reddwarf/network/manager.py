#    Copyright 2011 OpenStack LLC
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
from nova import log as logging
from nova.network import manager

from reddwarf.db import api as db_api
from reddwarf.dns import api as dns

FLAGS = flags.FLAGS
LOG = logging.getLogger("reddwarf.network.manager")


class FixedIpDnsEntries(manager.NetworkManager):
    """Subclass for adding DNS entries for ips to a network manager"""
    def __init__(self, *args, **kwargs):
        super(FixedIpDnsEntries, self).__init__(*args, **kwargs)
        self.dns_api = dns.API()

    def allocate_for_instance(self, context, **kwargs):
        """Handles allocating the various network resources for an instance.

        rpc.called by network_api
        """
        instance_id = kwargs.get('instance_id', '')
        admin_context = context.elevated()
        result = super(FixedIpDnsEntries, self).allocate_for_instance(context,
                                                                      **kwargs)
        self._allocate_dns_entry(admin_context, instance_id)
        return result

    def deallocate_for_instance(self, context, **kwargs):
        """Handles deallocating various network resources for an instance.

        rpc.called by network_api
        kwargs can contain fixed_ips to circumvent another db lookup
        """
        instance_id = kwargs.get('instance_id', '')
        self._deallocate_dns_entry(context, instance_id)
        super(FixedIpDnsEntries, self).deallocate_for_instance(context,
                                                               **kwargs)

    def _allocate_dns_entry(self, context, instance_id):
        """Creates a DNS entry for the compute instance"""
        instance_ref = self.db.instance_get(context, instance_id)
        address = self._find_address_used_for_dns(context, instance_id)
        if address:
            LOG.debug(_("Creating DNS entry for instance_id %i, address %s") %
                      (instance_id, address))
            self.dns_api.create_instance_entry(context, instance_ref, address)
        else:
            LOG.debug(_("No address found for instance_id %i") % instance_id)

    def _deallocate_dns_entry(self, context, instance_id):
        """Removes the dns entry. Must be called while fixed_ips exist."""
        address = self._find_address_used_for_dns(context, instance_id)
        if address:
            instance_ref = self.db.instance_get(context, instance_id)
            self.dns_api.delete_instance_entry(context, instance_ref, address)

    def _find_address_used_for_dns(self, context, instance_id):
        fixed_ips = db_api.fixed_ip_get_by_instance_for_network(context,
                                            instance_id, FLAGS.dns_bridge_name)
        if fixed_ips and len(fixed_ips) > 0:
            return fixed_ips[0].address
        return None


class FlatManager(FixedIpDnsEntries, manager.FlatManager):
    """Basic network where no vlans are used.

    FlatManager does not do any bridge or vlan creation.  The user is
    responsible for setting up whatever bridges are specified when creating
    networks through nova-manage. This bridge needs to be created on all
    compute hosts.

    The idea is to create a single network for the host with a command like:
    nova-manage network create 192.168.0.0/24 1 256. Creating multiple
    networks for for one manager is currently not supported, but could be
    added by modifying allocate_fixed_ip and get_network to get the a network
    with new logic instead of network_get_by_bridge. Arbitrary lists of
    addresses in a single network can be accomplished with manual db editing.

    If flat_injected is True, the compute host will attempt to inject network
    config into the guest.  It attempts to modify /etc/network/interfaces and
    currently only works on debian based systems. To support a wider range of
    OSes, some other method may need to be devised to let the guest know which
    ip it should be using so that it can configure itself. Perhaps an attached
    disk or serial device with configuration info.

    Metadata forwarding must be handled by the gateway, and since nova does
    not do any setup in this mode, it must be done manually.  Requests to
    169.254.169.254 port 80 will need to be forwarded to the api server.

    """


class FlatDHCPManager(FixedIpDnsEntries, manager.FlatDHCPManager):
    """Flat networking with dhcp.

    FlatDHCPManager will start up one dhcp server to give out addresses.
    It never injects network settings into the guest. It also manages bridges.
    Otherwise it behaves like FlatManager.

    """


class VlanManager(FixedIpDnsEntries, manager.VlanManager):
    """Vlan network with dhcp.

    VlanManager is the most complicated.  It will create a host-managed
    vlan for each project.  Each project gets its own subnet.  The networks
    and associated subnets are created with nova-manage using a command like:
    nova-manage network create 10.0.0.0/8 3 16.  This will create 3 networks
    of 16 addresses from the beginning of the 10.0.0.0 range.

    A dhcp server is run for each subnet, so each project will have its own.
    For this mode to be useful, each project will need a vpn to access the
    instances in its subnet.

    """
