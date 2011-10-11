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
from nova.volume.san import HpSanISCSIDriver


LOG = logging.getLogger("reddwarf.tests.volume.driver")

FLAGS = flags.FLAGS

TESTS_VOLUME_SIZE_MULTIPLIER = 256


class ISCSITestDriver(HpSanISCSIDriver):
    """ISCSILite Driver, basic ISCSI target features

    This is a lite ISCSI driver which uses all the client functionality
    within the HPSAN ISCSI driver but replaces the server side with calls
    to a software iscsitarget over ssh.

    """

    def assign_volume(self, volume_id, host):
        """Nothing to assign here."""
        pass

    def check_for_available_space(self, size):
        """Check for available volume space"""
        device_info = self._get_device_info()
        calc_info = self._calc_factors_space(device_info)
        LOG.debug("calculated info about space : %r" % calc_info)
        LOG.debug("checking_for_available_space %r : %r"
                  % (size, calc_info['prov_avail']))
        return (size <= calc_info['prov_avail'])

    def check_for_setup_error(self):
        """Check for any errors at setup for fast fail"""
        pass

    def create_volume(self, volume):
        """Create a volume on the iscsitarget"""
        name = volume['name']
        # We only use this for testing, so its a hassle to make 1 GB volumes
        # for stuff. Instead, we make it a multiple of 128 megabytes.
        size = volume['size'] * TESTS_VOLUME_SIZE_MULTIPLIER
        id = volume['id']
        LOG.debug(_("Creating volume of size %s MB") % str(size))
        try:
            self._run_ssh("sudo mkdir -p /san")
            self._run_ssh("sudo dd if=/dev/zero of=/san/%s.img bs=1024k "
                          "count=%d" % (id, size))
        except exception.ProcessExecutionError as err:
            LOG.error(err)
            raise

    def delete_volume(self, volume):
        """Delete a volume on the iscsitarget"""
        try:
            self._run_ssh("sudo rm /san/%s.img" % volume['id'])
        except exception.ProcessExecutionError as err:
            LOG.error(err)
            raise

    def create_export(self, context, volume):
        """Make the volume available on the storage server"""
        self._ensure_iscsi_targets(context, FLAGS.san_ip)
        iscsi_target = self.db.volume_allocate_iscsi_target(context,
                                                      volume['id'],
                                                      FLAGS.san_ip)
        try:
            # Create a target with the specified id
            self._run_ssh("sudo ietadm --op new --tid=%s --params " \
                          "Name=iqn.2011-06.reddwarf.com:%s"
                          % (iscsi_target, volume['id']))
            # Create a LUN on the target and define storage
            self._run_ssh("sudo ietadm --op new --tid=%s --lun=0 " \
                          "--params Path=/san/%s.img,Type=fileio"
                          % (iscsi_target, volume['id']))
            # Update CHAP user info for the target
            self._run_ssh("sudo ietadm --op new --tid=%s --user --params" \
                          " IncomingUser=username,Password=password1234"
                          % iscsi_target)
        except exception.ProcessExecutionError as err:
            LOG.error(err)
            raise

    def get_storage_device_info(self):
        """Returns the storage device information."""
        device_info = self._get_device_info()
        calc_info = self._calc_factors_space(device_info)
        LOG.debug("returning : %r" % calc_info)
        return calc_info

    def _get_device_info(self):
        """Get the raw data from the volume server"""
        # Value hard coded to 20GBs (could change to a constant
        # value if needed)
        space_total = 20 * (1024 ** 3)

        # Find out how much space is used on volume server
        (std_out, std_err) = self._run_ssh("sudo du -m /san")
        cmd_list = std_out.split('\t')
        LOG.debug("cmd_list : %r" % cmd_list)

        # Offset only applies to the ISCSI Lite Driver per create_volume(128MB)
        offset = (1024 ** 3) * 2
        LOG.debug("offset : %r" % offset)
        raw_used = (int(cmd_list[0]) / TESTS_VOLUME_SIZE_MULTIPLIER) * offset
        LOG.debug("raw_space_used : %r" % raw_used)
        LOG.debug("space_total : %r" % space_total)
        LOG.debug("spaceAvail : %r" % (space_total - raw_used))

        return {'name': 'ISCSI test class',
                        'type': self.__class__.__name__,
                        'spaceTotal': space_total,
                        'spaceAvail': space_total - raw_used}

    def remove_export(self, context, volume):
        """Remove the export on the storage server"""
        tid = self.db.volume_get_iscsi_target_num(context, volume['id'])
        try:
            self._run_ssh("sudo ietadm --op delete --tid=%s" % tid)
        except exception.ProcessExecutionError as err:
            LOG.error(err)
            raise
        # TODO(rnirmal): The target doesn't seem to get deleted from the db

    def ensure_export(self, context, volume):
        """Make sure existing volumes are exported"""
        pass

    def unassign_volume(self, volume_id, host):
        """Nothing to un-assign here."""
        pass

    def update_info(self, volume_ref):
        """Nothing to update"""
        pass
