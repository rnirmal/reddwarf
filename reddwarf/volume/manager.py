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
Volume manager manages creating, attaching, detaching, and persistent storage.

Persistant storage volumes keep their state independent of instances.  You can
attach to an instance, terminate the instance, spawn a new instance (even
one from a different image) and re-attach the volume with the same data
intact.

**Related Flags**

:volume_topic:  What :mod:`rpc` topic to listen to (default: `volume`).
:volume_manager:  The module name of a class derived from
                  :class:`manager.Manager` (default:
                  :class:`nova.volume.manager.AOEManager`).
:storage_availability_zone:  Defaults to `nova`.
:volume_group:  Name of the group that will contain exported volumes (default:
                `nova-volumes`)

"""

from nova import flags
from nova import log as logging
from nova import utils
from nova.notifier import api as notifier
from nova.volume import manager

from reddwarf import exception
from reddwarf.utils import poll_until

LOG = logging.getLogger('reddwarf.volume.manager')
FLAGS = flags.FLAGS

def publisher_id(host=None):
    return notifier.publisher_id("volume", host)


class ReddwarfVolumeManager(manager.VolumeManager):
    """Extends Nova Volume Manager with extended capabilities"""

    def __init__(self, volume_driver=None, *args, **kwargs):
        """Load the driver from the one specified in args, or from flags."""
        super(ReddwarfVolumeManager, self).__init__(*args, **kwargs)

    def _verify_available_space(self, context, volume_id, size):
        vol_avail = self.driver.check_for_available_space(size)
        if not vol_avail:
            LOG.error(_("Cannot allocate requested volume size. "
                        "requested size: %(size)sG") % locals())
            self.db.volume_update(context, volume_id, {'status': 'error'})
            raise exception.VolumeProvisioningError(volume_id=volume_id)

    def assign_volume(self, context, volume_id, host):
        """Assigns a created volume to a host (usually a compute node)."""
        self.driver.assign_volume(volume_id, host)

    def create_volume(self, context, volume_id, snapshot_id=None):
        """Creates and exports the volume."""
        #TODO (rnirmal): Need to somehow remove the extra db call
        context = context.elevated()
        volume_ref = self.db.volume_get(context, volume_id)
        self._verify_available_space(context, volume_id, volume_ref['size'])
        return super(ReddwarfVolumeManager, self).create_volume(context,
                                                                volume_id,
                                                                snapshot_id)

    def delete_volume_when_available(self, context, volume_id, time_out):
        """Waits until the volume is available and then deletes it."""
        poll_until(lambda: self.db.volume_get(context, volume_id),
                         lambda volume: volume['status'] == 'available',
                         sleep_time=1, time_out=time_out)
        self.delete_volume(context, volume_id)

    def check_for_available_space(self, context, size):
        """Check the device for available space for a Volume"""
        return self.driver.check_for_available_space(size)

    def get_storage_device_info(self, context):
        """Returns the storage device information."""
        return self.driver.get_storage_device_info()

    def unassign_volume(self, context, volume_id, host):
        """
        Un-Assigns an existing volume from a host (usually a compute node).
        """
        self.driver.unassign_volume(volume_id, host)

    def resize(self, context, volume_id, size):
        """Resize an existing volume to the specified size"""
        context = context.elevated()
        volume_ref = self.db.volume_get(context, volume_id)
        old_size = volume_ref['size']
        space_required = int(size) - int(old_size)
        self._verify_available_space(context, volume_id, space_required)
        self.db.volume_update(context, volume_id, {'status': 'resizing'})
        try:
            LOG.info("Resizing volume %(volume_id)s from %(old_size)sGB to "
                     "%(size)sGB" % locals())
            self.driver.resize(volume_ref, size)
            self.db.volume_update(context, volume_id,
                                  {'size': int(size), 'status': 'resized'})
            notifier.notify(publisher_id(self.host),
                            'volume.resize', notifier.INFO,
                            "Completed the volume resize")
        except Exception as e:
            LOG.error(e)
            self.db.volume_update(context, volume_id, {'status': 'error'})
            notifier.notify(publisher_id(self.host),
                            'volume.resize.resize',
                            notifier.ERROR,
                            "Error re-sizing volume %s" % volume_id)
            raise exception.VolumeProvisioningError(volume_id=volume_id)
