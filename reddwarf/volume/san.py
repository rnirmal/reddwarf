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
"""
Drivers for san-stored volumes.

The unique thing about a SAN is that we don't expect that we can run the volume
controller on the SAN hardware.  We expect to access it over SSH or some API.
"""

import os
import re
import paramiko
import pexpect
import random
from eventlet import greenthread
from eventlet import pools

from nova import exception as nova_exception
from nova import flags
from nova import log as logging
from nova import utils
from nova.utils import ssh_execute
from nova.volume import san as nova_san

from reddwarf import exception
from reddwarf.utils import poll_until
from reddwarf.volume.driver import ReddwarfISCSIDriver

LOG = logging.getLogger("reddwarf.volume.san")
FLAGS = flags.FLAGS
flags.DEFINE_string('san_port', '3260',
                    'Port of SAN controller')
flags.DEFINE_integer('san_network_raid_factor', 2,
                     'San network RAID factor')
flags.DEFINE_integer('san_max_provision_percent', 70,
                     'Max percentage of the total SAN space to be provisioned')
flags.DEFINE_integer('ssh_min_pool_conn', 2,
                     'Minimum ssh pooled connections')
flags.DEFINE_integer('ssh_max_pool_conn', 2,
                     'Maximum ssh connections in the pool')
flags.DEFINE_integer('ssh_conn_timeout', 30,
                     'SSH connection timeout in seconds')


class SSHPool(pools.Pool):
    """A simple eventlet pool to hold ssh clients"""

    def __init__(self, *args, **kwargs):
        super(SSHPool, self).__init__(*args, **kwargs)

    def create(self):
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            if FLAGS.san_password:
                ssh.connect(FLAGS.san_ip,
                            port=FLAGS.san_ssh_port,
                            username=FLAGS.san_login,
                            password=FLAGS.san_password,
                            timeout=FLAGS.ssh_conn_timeout)
            elif FLAGS.san_privatekey:
                privatekeyfile = os.path.expanduser(FLAGS.san_privatekey)
                privatekey = paramiko.RSAKey.from_private_key_file(privatekeyfile)
                ssh.connect(FLAGS.san_ip,
                            port=FLAGS.san_ssh_port,
                            username=FLAGS.san_login,
                            pkey=privatekey,
                            timeout=FLAGS.ssh_conn_timeout)
            else:
                raise nova_exception.Error(_("Specify san_password or san_privatekey"))
            # Paramiko by default sets the socket timeout to 0.1 seconds,
            # ignoring what we set thru the sshclient. This doesn't help for
            # keeping long lived connections. Hence we have to bypass it, by
            # overriding it after the transport is initialized. We are setting
            # the sockettimeout to None and setting a keepalive packet so that,
            # the server will keep the connection open. All that does is send
            # a keepalive packet every ssh_conn_timeout seconds.
            transport = ssh.get_transport()
            transport.sock.settimeout(None)
            transport.set_keepalive(FLAGS.ssh_conn_timeout)
            return ssh
        except Exception as e:
            msg = "Error connecting via ssh: %s" % e
            LOG.error(_(msg))
            raise paramiko.SSHException(msg)


class DiscoveryInfo(object):

    id_in_target = re.compile('.+?:([0-9]+)$')

    def __init__(self, portal, target):
        self.portal = portal
        self.target = target
        match = DiscoveryInfo.id_in_target.search(target)
        self.volume_id = long(match.group(1))


class InitiatorLoginError(nova_exception.Error):
    """Occurs when the initiator fails to login for some reason."""
    pass


class ReddwarfSanISCSIDriver(ReddwarfISCSIDriver, nova_san.SanISCSIDriver):
    """ Base class for SAN-style storage volumes

    A SAN-style storage value is 'different' because the volume controller
    probably won't run on it, so we need to access is over SSH or another
    remote protocol.
    """

    def __init__(self, *args, **kwargs):
        super(ReddwarfSanISCSIDriver, self).__init__(*args, **kwargs)
        self.sshpool = None

    def _run_ssh(self, command, check_exit_code=True, attempts=1):
        if not self.sshpool:
            self.sshpool = SSHPool(min_size=FLAGS.ssh_min_pool_conn,
                                   max_size=FLAGS.ssh_max_pool_conn)
        try:
            total_attempts = attempts
            with self.sshpool.item() as ssh:
                max_sleep = FLAGS.max_sleep_between_shell_tries * 100
                while attempts > 0:
                    attempts -= 1
                    try:
                        ret = ssh_execute(ssh, command,
                                          check_exit_code=check_exit_code)
                        return ret
                    except Exception as e:
                        LOG.error(e)
                        greenthread.sleep(random.randint(20, max_sleep) / 100.0)
                raise paramiko.SSHException("SSH Command failed after '%r' "
                                            "attempts: '%s'"
                                            % (total_attempts, command))
        except Exception as e:
            LOG.error(_("Error running ssh command: %s" % command))
            raise e


class ReddwarfHpSanISCSIDriver(ReddwarfSanISCSIDriver,
                               nova_san.HpSanISCSIDriver):
    """Executes commands relating to HP/Lefthand SAN ISCSI volumes.

    We use the CLIQ interface, over SSH.

    Rough overview of CLIQ commands used:

    :createVolume:    (creates the volume)
    :deleteVolume:    (deletes the volume)
    :assignVolumeToServer:  (assigns a volume to a given server)
    :getVolumeInfo:    (to discover the IQN etc)
    :getClusterInfo:    (to discover the iSCSI target IP address)

    """

    def _cliq_run(self, verb, cliq_args):
        """Runs a CLIQ command over SSH, without doing any result parsing"""
        # TODO(rnirmal): Bulk copy-paste. Needs to be merged back into nova
        cliq_arg_strings = []
        for k, v in cliq_args.items():
            cliq_arg_strings.append(" %s=%s" % (k, v))
        cmd = verb + ''.join(cliq_arg_strings)

        return self._run_ssh(cmd, attempts=FLAGS.num_tries)

    def _cliq_get_cluster_info(self, cluster_name):
        """Queries for info about the cluster (including IP)"""

        result_xml = super(ReddwarfHpSanISCSIDriver,
                           self)._cliq_get_cluster_info(cluster_name)

        # Parse the result into a dictionary
        cluster_info = {}
        cluster_node = result_xml.find("response/cluster")
        cluster_info['name'] = cluster_node.attrib.get("name")
        cluster_info['spaceTotal'] = cluster_node.attrib.get("spaceTotal")
        cluster_info['spaceAvail'] = cluster_node.attrib \
                                                 .get("unprovisionedSpace")
        cluster_info['vip'] = result_xml.find("response/cluster/vip") \
                                        .attrib.get('ipAddress')
        return cluster_info

    def assign_volume(self, volume_id, host):
        """
        Assign any created volume to a compute node/host so that it can be
        used from that host. HP VSA requires a volume to be assigned
        to a server
        """
        cliq_args = {}
        cliq_args['volumeName'] = volume_id
        cliq_args['serverName'] = host
        self._cliq_run_xml("assignVolumeToServer", cliq_args)

    def check_for_available_space(self, size):
        """Check for available volume space"""
        cluster_info = self._cliq_get_cluster_info(FLAGS.san_clustername)
        calc_info = self._calc_factors_space(cluster_info)
        return (size <= calc_info['prov_avail'])

    def create_volume(self, volume_ref):
        """Creates a volume."""
        # TODO(rnirmal): Bulk copy-paste. Needs to be merged back into nova
        cliq_args = {}
        cliq_args['clusterName'] = FLAGS.san_clustername
        cliq_args['thinProvision'] = '1' if FLAGS.san_thin_provision else '0'
        # Using volume id for name to guarantee uniqueness
        cliq_args['volumeName'] = volume_ref['id']
        volume_size = int(volume_ref['size'])
        if volume_size <= 0:
            raise ValueError("Invalid volume size.")
        cliq_args['size'] = '%sGB' % volume_size
        cliq_args['description'] = '"%s"' % volume_ref['display_description']

        self._cliq_run_xml("createVolume", cliq_args)

    def unassign_volume(self, volume_id, host):
        """Unassign a volume that's associated with a server."""
        cliq_args = {}
        cliq_args['volumeName'] = volume_id
        cliq_args['serverName'] = host
        self._cliq_run_xml("unassignVolumeToServer", cliq_args)

    def delete_volume(self, volume):
        """Deletes a volume."""
        # TODO(rnirmal): Bulk copy-paste. Needs to be merged back into nova
        cliq_args = {}
        cliq_args['volumeName'] = volume['id']
        cliq_args['prompt'] = 'false'  # Don't confirm
        self._cliq_run_xml("deleteVolume", cliq_args)

    def ensure_export(self, context, volume):
        """Ensure export is not applicable unlike other drivers."""
        pass

    def create_export(self, context, volume):
        """Create export is not applicable unlike other drivers.

        Check assign_volume() instead
        """
        pass

    def _calc_factors_space(self, cluster_info):
        """Calculate the given the cluster_info of space total and available"""
        space_total = float(cluster_info['spaceTotal'])
        space_avail = float(cluster_info['spaceAvail'])
        LOG.debug("Volume space Total : %r" % space_total)
        LOG.debug("Volume space Avail : %r" % space_avail)

        # Calculate the available space and total space based on factors
        G = 1024 ** 3
        raid_factor = float(FLAGS.san_network_raid_factor) * G
        LOG.debug("Volume raid factor : %.2f" % raid_factor)

        # Use the calculated factor to determine total/avail
        factor_total = space_total / raid_factor
        factor_avail = space_avail / raid_factor
        LOG.debug("Volume factor Total : %rGBs" % factor_total)
        LOG.debug("Volume factor Avail : %rGBs" % factor_avail)

        # Take the max provisional percent of device into calculation
        percent = float(FLAGS.san_max_provision_percent) / 100.0
        LOG.debug("Volume san_max_provision_percent : %r" % percent)

        # How much are we allowed to use?
        # Total calculated provisional space for the device
        prov_total = float(factor_total * percent)
        # Total calculated used space on the device
        prov_used = (factor_total - factor_avail)
        LOG.debug("Volume total space size : %rGBs" % prov_total)
        LOG.debug("Volume used space size : %rGBs" % prov_used)
        # Total calculated available space on the device
        prov_avail = prov_total - prov_used
        LOG.debug("Volume available_space : %rGBs" % prov_avail)

        # Create the dictionary of values to return
        return {'name': cluster_info['name'],
                'type': self.__class__.__name__,
                'raw_total': space_total,
                'raw_avail': space_avail,
                'prov_avail': prov_avail,
                'prov_total': prov_total,
                'prov_used': prov_used,
                'percent': percent}

    def get_storage_device_info(self):
        """Returns the storage device information."""
        cluster_info = self._cliq_get_cluster_info(FLAGS.san_clustername)
        return self._calc_factors_space(cluster_info)

    @staticmethod
    def _get_discovery_info():
        """Given a volume ID, returns list of matching DiscoveryInfo items.

        The cmd:
        iscsiadm -m discovery -t st -p {ip}

          returns stuff like this:
        10.0.2.15:3260,1 iqn.2011-06.reddwarf.com:target1

        This method returns a list of named tuples with the portal, the target,
        and the volume ID.

        """
        cmd = "sudo iscsiadm -m discovery -t st -p %s" % FLAGS.san_ip
        child = pexpect.spawn(cmd)
        list = []
        while True:
            try:
                child.expect('([0-9\\.]+:[0-9]+)\\,[0-9]+[ \t]*(.+?:[0-9]+)\\r')
                info = DiscoveryInfo(*child.match.groups())
                list.append(info)
            except pexpect.EOF:
                break
        return list

    def _attempt_discovery(self, context, volume):
        volume_id = long(volume['id'])
        for info in self._get_discovery_info():
            if info.volume_id == volume_id and FLAGS.san_ip in info.portal:
                return {"target_iqn": info.target,
                        "target_portal": info.portal}
        else:
            return None

    def get_iscsi_properties_for_volume(self, context, volume):
        try:
            # Assume each discovery attempt takes roughly two seconds.
            return poll_until(lambda: self._attempt_discovery(context,
                                                                     volume),
                                    lambda properties: properties is not None,
                                    sleep_time=3,
                                    time_out=5 * FLAGS.num_tries)
        except exception.PollTimeOut:
            raise exception.ISCSITargetNotDiscoverable(volume_id=volume['id'])

    def remove_export(self, context, volume):
        """Remove export is not applicable unlike other drivers.

        Check unassign_volume() instead
        """
        pass

    def resize(self, volume, new_size):
        """Resize the existing volume to the specified size"""
        LOG.debug("Resizing Volume:%s from %sGB to %sGB"
                  % (volume['id'], volume['size'], new_size))
        cliq_args = {}
        cliq_args['volumeName'] = volume['id']
        # TODO(rnirmal): We may need to double check the current size, incase
        # the user is attempting to decrease the size and the current size
        # as reported from the san is different than the nova database.
        volume_size = int(new_size)
        if volume_size <= 0:
            raise ValueError("Invalid volume size.")
        cliq_args['size'] = '%sGB' % volume_size
        self._cliq_run_xml("modifyVolume", cliq_args)
