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

import time
from tests import util
from nova.exception import VolumeNotFound

GROUP='dbaas.guest.initialize.failure'


from datetime import datetime

from proboscis import after_class
from proboscis import before_class
from proboscis import test
from proboscis.asserts import assert_equal
from proboscis.asserts import assert_false
from proboscis.asserts import assert_true
from proboscis.asserts import assert_is_not_none
from proboscis.asserts import fail
from proboscis.decorators import expect_exception
from proboscis.decorators import time_out

from novaclient.exceptions import NotFound
from nova import context, utils
from reddwarf.api.instances import _dbaas_mapping
from nova.compute import power_state
from reddwarf.api.instances import _dbaas_mapping
from reddwarf.db import api as dbapi
from nova import flags
from reddwarf.compute.manager import VALID_ABORT_STATES
from reddwarf.compute.manager import ReddwarfInstanceMetaData
from tests.util import test_config
from tests.util import test_config
from tests.util import check_database
from tests.util import create_dns_entry
from tests.util import create_test_client
from tests.util import process
from tests.util import restart_compute_service
from tests.util import string_in_list
from tests.util import TestClient
from tests.util.users import Requirements


FLAGS = flags.FLAGS

# TODO(tim.simpson): Tests are needed for the following cases:
#
# When provisioning an instance:
# A volume fails to provision:
#     This can be because there is not sufficient space or the account limits
#     are exceeded. There is anothet trickier third case where the volume
#     might be provisioning but is timed out, and must be deleted.
#   In these cases the status must be FAIL. No resources should be counted
#     against the user's account, unless it was via a time-out (this is so the
#     volume can finish creating and we can look at it). However when deleted
#     the volume should also be deleted, and after this point not count against
#     the user's quotas.
#
# The compute instance fails to provision, as an error occurs. The state must
#     be set to FAIL. In this case the compute instance is set to suspended
#     but not deleted (if it even exists in any state) so this may or may not
#     count against a user's quotas
#   When deleted the instance should vanish along with the volumes and all
#     quotas be returned to where they were before.
#
# The guest install times out. In this case the state must be set to FAIL and
#     must stay there! When delete is called, the instance and volume should
#     dissappear.
#
# In addition to GETs and LISTs returning FAIL as the state, attempts to
# add databases should fail.
#

@test(groups=[GROUP],
      depends_on_groups=["services.initialize"])
class InstanceTest(object):
    """Stores new instance information used by dependent tests."""

    def __init__(self):
        self.db = utils.import_object(FLAGS.db_driver)
        self.user = None  # The user instance who owns the instance.
        self.dbaas = None  # The rich client instance used by these tests.
        self.dbaas_flavor = None # The flavor object of the instance.
        self.dbaas_flavor_href = None  # The flavor of the instance.
        self.dbaas_image = None  # The image used to create the instance.
        self.dbaas_image_href = None  # The link of the image.
        self.id = None  # The ID of the instance in the database.
        self.name = None  # Test name, generated each test run.
        self.volume = {'size': 1} # The volume the instance will have.
        self.initial_result = None # The initial result from the create call.

    def init(self, name_prefix):
        """Sets up the client."""
        # Find user, create DBAAS rich client
        self.user = test_config.users.find_user(Requirements(is_admin=True))
        self.dbaas = create_test_client(self.user)
        # Get image
        result = self.dbaas.find_image_and_self_href(test_config.dbaas_image)
        self.dbaas_image, self.dbaas_image_href = result
        # Get flavor
        result = self.dbaas.find_flavor_and_self_href(flavor_id=1)
        self.dbaas_flavor, self.dbaas_flavor_href = result
        self.name = name_prefix + str(datetime.now())
        # TODO: Grab initial amount of disk space left in account quota

    def _assert_status_failure(self, result):
        """Checks if status==FAILED, plus asserts REST API is in sync."""
        if result[0].state == power_state.BUILDING:
            assert_true(
                result[1].status == _dbaas_mapping[power_state.BUILDING] or
                result[1].status == _dbaas_mapping[power_state.FAILED],
                "Result status from API should only be BUILDING or FAILED"
                " at this point but was %s" % result[1].status)
            return False
        else:
            # After building the only valid state is FAILED (because
            # we've destroyed the instance).
            assert_equal(result[0].state, power_state.FAILED)
            # Make sure the REST API agrees.
            assert_equal(result[1].status, _dbaas_mapping[power_state.FAILED])
            return True

    def _assert_volume_is_eventually_deleted(self, time_out=3*60):
        def volume_not_found():
            try:
                self.db.volume_get(context.get_admin_context(), self.volume_id)
                return False
            except VolumeNotFound:
                return True
        utils.poll_until(volume_not_found, sleep_time=1, time_out=time_out)

    def _create_instance(self):
        """Make call to create a instance."""
        self.initial_result = self.dbaas.instances.create(
            name=self.name,
            flavor_id=self.dbaas_flavor_href,
            volume=self.volume,
            databases=[{"name": "firstdb", "character_set": "latin2",
                        "collate": "latin2_general_ci"}])
        result = self.initial_result
        self.id = result.id
        assert_equal(result.status, _dbaas_mapping[power_state.BUILDING])

    def _get_status_tuple(self):
        """Grabs the db guest status and the API instance status."""
        return (dbapi.guest_status_get(self.id),
                self.dbaas.instances.get(self.id))

    def _delete_instance(self):
        self.dbaas.instances.delete(self.id)
        attempts = 0
        try:
            time.sleep(1)
            result = True
            while result is not None:
                attempts += 1
                result = self.dbaas.instances.get(self.id)
                assert_equal(_dbaas_mapping[power_state.SHUTDOWN],
                             result.status)
        except NotFound:
            pass
        except Exception as ex:
            fail("A failure occured when trying to GET instance %s"
                 " for the %d time: %s" % (str(self.id), attempts, str(ex)))

    def _get_compute_instance_state(self):
        return self.db.instance_get(context.get_admin_context(),
                                    self.id).state

    def wait_for_rest_api_to_show_status_as_failed(self, time_out):
        utils.poll_until(self._get_status_tuple, self._assert_status_failure,
                         sleep_time=1, time_out=time_out)

    def wait_for_compute_instance_to_suspend(self):
        """Polls until the compute instance is known to be suspended."""
        utils.poll_until(self._get_compute_instance_state,
                         lambda state : state in VALID_ABORT_STATES,
                         sleep_time=1,
                         time_out=FLAGS.reddwarf_instance_suspend_time_out)


#TODO: Change volume timeout to something very low, and make sure the instance
# is set to fail.  If it isn't possible to make sure the volume never
# provisions this could also be a reaper test.

VOLUME_TIME_OUT=30
@test(groups=[GROUP, GROUP + ".volume"],
      depends_on_groups=["services.initialize"])
class VerifyManagerAbortsInstanceWhenVolumeFails(InstanceTest):

    @before_class
    def setUp(self):
        """Sets up the client."""
        test_config.volume_service.stop()
        assert_false(test_config.volume_service.is_running)
        restart_compute_service(['--reddwarf_volume_time_out=%d'
                                 % VOLUME_TIME_OUT])
        self.init("TEST_FAIL_VOLUME_")

    @after_class
    def tearDown(self):
        """Be nice to other tests and restart the compute service normally."""
        test_config.volume_service.start()
        restart_compute_service()

    @test
    def create_instance(self):
        """Create a new instance."""
        self._create_instance()
        # Use an admin context to avoid the possibility that in between the
        # previous line and this one the request goes through and the instance
        # is deleted.
        metadata = ReddwarfInstanceMetaData(self.db,
            context.get_admin_context(), self.id)
        self.volume_id = metadata.volume_id

    @test(depends_on=[create_instance])
    def wait_for_failure(self):
        """Make sure the Reddwarf Compute Manager FAILS a timed-out volume."""
        self.wait_for_rest_api_to_show_status_as_failed(VOLUME_TIME_OUT + 30)

    @test(depends_on=[wait_for_failure])
    def delete_instance(self):
        """Delete the instance."""
        #TODO: Put this in once the OpenVZ driver's destroy() method doesn't
        # raise an exception when the volume doesn't exist.
        #self._delete_instance()

    @test(depends_on=[wait_for_failure])
    def volume_should_be_deleted(self):
        """Make sure the volume is gone."""
        #TODO: Test that the volume, when it comes up, is eventually deleted
        # by the Reaper.
        #@expect_exception(VolumeNotFound)
        #self._assert_volume_is_eventually_deleted()


#TODO: Find some way to get the compute instance creation to fail.

GUEST_INSTALL_TIMEOUT = 60 * 2

@test(groups=[GROUP, GROUP + ".guest"],
      depends_on_groups=["services.initialize"])
class VerifyManagerAbortsInstanceWhenGuestInstallFails(InstanceTest):
    """Stores new instance information used by dependent tests."""

    @before_class
    def setUp(self):
        """Sets up the client."""
        restart_compute_service(['--reddwarf_guest_initialize_time_out=%d'
                                 % GUEST_INSTALL_TIMEOUT])
        self.init("TEST_FAIL_GUEST_")

    @after_class
    def tearDown(self):
        """Be nice to other tests and restart the compute service normally."""
        restart_compute_service()

    @test
    def create_instance(self):
        self._create_instance()
        metadata = ReddwarfInstanceMetaData(self.db,
            context.get_admin_context(), self.id)
        self.volume_id = metadata.volume_id
        assert_is_not_none(metadata.volume)
        

    @test(depends_on=[create_instance])
    @time_out(60 * 4)
    def wait_for_compute_instance_to_start(self):
        """Wait for the compute instance to begin."""
        while True:
            status, err = process("sudo vzctl status %s | awk '{print $5}'"
                                  % str(self.id))

            if not string_in_list(status, ["running"]):
                time.sleep(5)
            else:
                assert_equal("running", status.strip())
                break


    @test(depends_on=[create_instance])
    @time_out(60 * 4)
    def wait_for_pid(self):
        """Wait for instance PID."""
        pid = None
        while pid is None:
            guest_status = dbapi.guest_status_get(self.id)
            rest_api_result = self.dbaas.instances.get(self.id)
            out, err = process("pstree -ap | grep init | cut -d',' -f2 | vzpid - | grep %s | awk '{print $1}'"
                                % str(self.id))
            pid = out.strip()
            if not pid:
                # Make sure the guest status is BUILDING during this time.
                assert_equal(guest_status.state, power_state.BUILDING)
                # REST API should return BUILDING as the status as well.
                assert_equal(_dbaas_mapping[power_state.BUILDING],
                             rest_api_result.status)
                time.sleep(10)

    @test(depends_on=[wait_for_compute_instance_to_start, wait_for_pid])
    def should_have_created_volume(self):
        #TODO: Make sure volume exists here
        #TODO: Make sure memory is allocated
        pass

    @test(depends_on=[should_have_created_volume])
    def destroy_guest_and_wait_for_failure(self):
        """Make sure the Reddwarf Compute Manager FAILS a timed-out guest."""

        # Utterly kill the guest install.
        process("sudo rm -rf /vz/private/%s/bin" % str(self.id))

        # Make sure that before the timeout expires the guest state in the
        # internal API and the REST API instance status is set to FAIL.
        self.wait_for_rest_api_to_show_status_as_failed(
            time_out=GUEST_INSTALL_TIMEOUT + 30)

        # At this point there is a tiny chance the compute API will spend a
        # little bit of time trying to suspend the instance. We need it to
        # because, while in this case we know the guest is dead, in the real
        # world where this might happen for less-predictable reasons we want
        # to make sure the misbehaving or just slow Nova-Guest daemon doesn't
        # change its status to something besides FAILED before the instance is
        # shut-off. So we have to make sure that the instance turns off, and
        # the manager sets the guest state to FAILED afterwards.
        self.wait_for_compute_instance_to_suspend()

        #TODO(tim.simpson): It'd be really cool if we could somehow coax the
        #                   guest to repeatedly setting its state in the db to
        #                   something besides failed, so we could assert that
        #                   no matter what after it was suspended it was set
        #                   to such.  Although maybe that's overkill.
        self._assert_status_failure(self._get_status_tuple())

    @test(depends_on=[destroy_guest_and_wait_for_failure])
    def delete_instance(self):
        self._delete_instance()

    @test(depends_on=[delete_instance])
    def make_sure_resources_are_removed(self):
        #TODO: Make sure the initial disk space is back to where it was,
        # i.e. the associated volume was deleted.
        #Make sure memory is where it was.
        self._assert_volume_is_eventually_deleted(3*60)
