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
Drivers for volumes.

"""

import time
import os

import pexpect

from nova import context
from nova import exception as nova_exception
from nova import flags
from nova import log as logging
from nova import utils
from nova.volume import driver as nova_driver

from reddwarf import exception

LOG = logging.getLogger("nova.volume.driver")
FLAGS = flags.FLAGS
flags.DEFINE_integer('num_tries', 3,
                    'number of times to attempt to run flakey shell commands')
flags.DEFINE_integer('max_sleep_between_shell_tries', 5,
                     'Max. seconds to sleep between shell retries')
flags.DEFINE_integer('volume_format_timeout', 120,
                     'timeout for formatting volumes')
flags.DEFINE_string('volume_fstype', 'ext3',
                    'The file system type used to format and mount volumes.')
flags.DEFINE_string('format_options', '-m 5',
                    'String specifying various options passed to mkfs')
flags.DEFINE_string('mount_options', 'noatime',
                    'String specifying various options passed to mount')


class ReddwarfVolumeDriver(nova_driver.VolumeDriver):
    """Executes commands relating to Volumes."""
    def __init__(self, execute=utils.execute,
                 sync_exec=utils.execute, *args, **kwargs):
        super(ReddwarfVolumeDriver, self).__init__(execute=execute, sync_exec=sync_exec,
                                           *args, **kwargs)

    def assign_volume(self, volume_id, host):
        """
        Assign the volume to the specified compute host so that it could
        be potentially used in discovery in certain drivers
        """
        pass

    def check_for_available_space(self, size):
        """Call to check the size is available for volume"""
        pass

    def check_for_client_setup_error(self):
        """
        Returns and error if the client is not setup properly to
        talk to the specific volume management service.
        """
        pass

    def get_volume_uuid(self, device_path):
        """Returns the UUID of a device given that device path.

        The returned UUID is expected to be hex in five groups with the lengths
        8,4,4,4 and 12.
        Example:
        fd575a25-f9d9-4e7f-aafd-9c2b92e9ec4c

        If the device_path doesn't match anything, DevicePathInvalidForUuid
        is raised.

        """
        child = pexpect.spawn("sudo blkid " + device_path)
        i = child.expect(['UUID="([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-'
                          '[0-9a-f]{4}-[0-9a-f]{12})"', pexpect.EOF])
        if i > 0:
            raise exception.DevicePathInvalidForUuid(device_path=device_path)
        return child.match.groups()[0]

    def unassign_volume(self, volume_id, host):
        """Some drivers need this to associate a volume to a host."""
        pass

    def _check_device_exists(self, device_path):
        """Check that the device path exists.

        Verify that the device path has actually been created and can report
        it's size, only then can it be available for formatting, retry
        num_tries to account for the time lag.
        """
        try:
            utils.execute('sudo', 'blockdev', '--getsize64', device_path,
                          attempts=FLAGS.num_tries)
        except nova_exception.ProcessExecutionError:
            raise nova_exception.InvalidDevicePath(path=device_path)

    def _check_format(self, device_path):
        """Checks that an unmounted volume is formatted."""
        child = pexpect.spawn("sudo dumpe2fs %s" % device_path)
        try:
            i = child.expect(['has_journal', 'Wrong magic number'])
            if i == 0:
                return
            raise IOError('Device path at %s did not seem to be %s.' %
                          (device_path, FLAGS.volume_fstype))
        except pexpect.EOF:
            raise IOError("Volume was not formatted.")
        child.expect(pexpect.EOF)

    def _format(self, device_path):
        """Calls mkfs to format the device at device_path."""
        cmd = "sudo mkfs -t %s %s %s" % (FLAGS.volume_fstype,
                                         FLAGS.format_options, device_path)
        child = pexpect.spawn(cmd, timeout=FLAGS.volume_format_timeout)
        child.expect("(y,n)")
        child.sendline('y')
        child.expect(pexpect.EOF)

    def format(self, device_path):
        """Formats the device at device_path and checks the filesystem."""
        self._check_device_exists(device_path)
        self._format(device_path)
        self._check_format(device_path)

    def mount(self, device_path, mount_point):
        if not os.path.exists(mount_point):
            os.makedirs(mount_point)
        cmd = "sudo mount -t %s -o %s %s %s" % (FLAGS.volume_fstype,
                                                FLAGS.mount_options,
                                                device_path, mount_point)
        child = pexpect.spawn(cmd)
        child.expect(pexpect.EOF)

    def unmount(self, mount_point):
        if os.path.exists(mount_point):
            cmd = "sudo umount %s" % mount_point
            child = pexpect.spawn(cmd)
            child.expect(pexpect.EOF)

    def resize(self, volume, new_size):
        """Resize the existing volume to the specified size"""
        pass

    def rescan(self, volume):
        """Rescan the client storage connection"""
        pass

    def resize_fs(self, device_path):
        """Resize the filesystem on the specified device"""
        self._check_device_exists(device_path)
        try:
            self._execute("sudo", "resize2fs", device_path)
        except nova_exception.ProcessExecutionError as err:
            LOG.error(err)
            raise nova_exception.Error("Error resizing the filesystem: %s"
                                       % device_path)


class ReddwarfISCSIDriver(ReddwarfVolumeDriver, nova_driver.ISCSIDriver):
    """Executes commands relating to ISCSI volumes.

    We make use of model provider properties as follows:

    :provider_location:    if present, contains the iSCSI target information
                           in the same format as an ietadm discovery
                           i.e. '<ip>:<port>,<portal> <target IQN>'

    :provider_auth:    if present, contains a space-separated triple:
                       '<auth method> <auth username> <auth password>'.
                       `CHAP` is the only auth_method in use at the moment.
    """

    def check_for_client_setup_error(self):
        """
        Returns an error if the client is not setup properly to
        talk to the iscsi target server.
        """
        try:
            self._execute("sudo", "iscsiadm", "-m", "discovery",
                          "-t", "st", "-p", FLAGS.san_ip)
        except nova_exception.ProcessExecutionError as err:
            LOG.fatal("Error initializing the volume client: %s" % err)
            raise nova_exception.VolumeServiceUnavailable()

    def _do_iscsi_discovery(self, volume):
        # TODO(rnirmal): Bulk copy-paste. Needs to be merged back into nova
        #TODO(justinsb): Deprecate discovery and use stored info
        #NOTE(justinsb): Discovery won't work with CHAP-secured targets (?)
        LOG.warn(_("ISCSI provider_location not stored, using discovery"))

        volume_name = volume['name']

        (out, _err) = self._execute('iscsiadm', '-m', 'discovery',
                                    '-t', 'sendtargets', '-p', volume['host'],
                                    run_as_root=True,
                                    attempts=FLAGS.num_tries)
        for target in out.splitlines():
            if FLAGS.iscsi_ip_prefix in target and volume_name in target:
                return target
        return None

    def _run_iscsiadm(self, iscsi_properties, iscsi_command, num_tries=1):
        # TODO(rnirmal): Bulk copy-paste. Needs to be merged back into nova
        (out, err) = self._execute('iscsiadm', '-m', 'node', '-T',
                                   iscsi_properties['target_iqn'],
                                   '-p', iscsi_properties['target_portal'],
                                   iscsi_command, run_as_root=True,
                                   attempts=num_tries)
        LOG.debug("iscsiadm %s: stdout=%s stderr=%s" %
                  (iscsi_command, out, err))
        return (out, err)

    def get_iscsi_properties_for_volume(self, context, volume):
        #TODO(tim.simpson) This method executes commands assuming the
        # nova-volume is on the same node as nova-compute.
        iscsi_properties = self._get_iscsi_properties(volume)
        if not iscsi_properties['target_discovered']:
            self._run_iscsiadm(iscsi_properties, ('--op', 'new'))
        return iscsi_properties

    def set_iscsi_auth(self, iscsi_properties):
        if iscsi_properties.get('auth_method', None):
            self._iscsiadm_update(iscsi_properties,
                                  "node.session.auth.authmethod",
                                  iscsi_properties['auth_method'])
            self._iscsiadm_update(iscsi_properties,
                                  "node.session.auth.username",
                                  iscsi_properties['auth_username'])
            self._iscsiadm_update(iscsi_properties,
                                  "node.session.auth.password",
                                  iscsi_properties['auth_password'])

    def discover_volume(self, context, volume):
        """Discover volume on a remote host."""
        # TODO(rnirmal): Bulk copy-paste. Needs to be merged back into nova
        iscsi_properties = self.get_iscsi_properties_for_volume(context,
                                                                volume)
        self.set_iscsi_auth(iscsi_properties)

        try:
            self._run_iscsiadm(iscsi_properties, "--login",
                               num_tries=FLAGS.num_tries)
        except nova_exception.ProcessExecutionError as err:
            LOG.error(err)
            raise nova_exception.Error(_("iSCSI device %s not found") %
                                        iscsi_properties['target_iqn'])

        mount_device = ("/dev/disk/by-path/ip-%s-iscsi-%s-lun-0" %
                        (iscsi_properties['target_portal'],
                         iscsi_properties['target_iqn']))
        return mount_device

    def undiscover_volume(self, volume):
        """Undiscover volume on a remote host."""
        # TODO(rnirmal): Bulk copy-paste. Needs to be merged back into nova
        iscsi_properties = self.get_iscsi_properties_for_volume(None, volume)
        self._iscsiadm_update(iscsi_properties, "node.startup", "manual")
        self._run_iscsiadm(iscsi_properties, "--logout")

    def rescan(self, volume):
        """Rescan the client storage connection"""

        iscsi_properties = self.get_iscsi_properties_for_volume(context.get_admin_context(),
                                                                volume)
        try:
            LOG.debug("ISCSI Properties: %s" % iscsi_properties)
            self._run_iscsiadm(iscsi_properties, "--rescan",
                               num_tries=FLAGS.num_tries)
            return ("/dev/disk/by-path/ip-%s-iscsi-%s-lun-0" %
                                   (iscsi_properties['target_portal'],
                                    iscsi_properties['target_iqn']))
        except nova_exception.ProcessExecutionError as err:
            LOG.error(err)
            raise nova_exception.Error(_("Error rescanning iscsi device: %s") %
                                       iscsi_properties['target_iqn'])
