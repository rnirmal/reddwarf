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

import gettext
import os
import json
import re
import sys
import time
import unittest
from tests import util

GROUP='dbaas.guest.initialize.failure'


from datetime import datetime
from nose.plugins.skip import SkipTest
from nose.tools import assert_true
from novaclient.exceptions import NotFound
from nova import context, utils
from nova.compute import power_state
from reddwarf.api.dbcontainers import _dbaas_mapping
from reddwarf.db import api as dbapi
from nova import flags

from reddwarf.compute.manager import VALID_ABORT_STATES

from tests.util import test_config
from proboscis.decorators import expect_exception
from proboscis.decorators import time_out
from proboscis import test
from tests.util import test_config
from tests.util import check_database
from tests.util import create_dns_entry
from tests.util import create_test_client
from tests.util import process
from tests.util.users import Requirements
from tests.util import string_in_list
from tests.util import TestClient

FLAGS = flags.FLAGS


class ContainerTestInfo(object):
    """Stores new container information used by dependent tests."""

    def __init__(self):
        self.dbaas = None  # The rich client instance used by these tests.
        self.dbaas_flavor = None # The flavor object of the container.
        self.dbaas_flavor_href = None  # The flavor of the container.
        self.dbaas_image = None  # The image used to create the container.
        self.dbaas_image_href = None  # The link of the image.
        self.id = None  # The ID of the instance in the database.
        self.initial_result = None # The initial result from the create call.
        self.name = None  # Test name, generated each test run.
        self.user = None  # The user instance who owns the container.

    def check_database(self, dbname):
        return check_database(self.id, dbname)

    def expected_dns_entry(self):
        """Returns expected DNS entry for this container.

        :rtype: Instance of :class:`DnsEntry`.

        """
        return create_dns_entry(container_info.user.auth_user,
                                container_info.id)


# The two variables are used below by tests which depend on a container
# existing.
container_info = ContainerTestInfo()
dbaas = None  # Rich client used throughout this test.



@test(groups=[GROUP],
      depends_on_groups=["services.initialize"])
class Setup(unittest.TestCase):

    def setUp(self):
        """Sets up the client."""
        global dbaas
        container_info.user = test_config.users.find_user(
            Requirements(is_admin=True))
        dbaas = create_test_client(container_info.user)

    def test_find_image(self):
        result = dbaas.find_image_and_self_href(test_config.dbaas_image)
        container_info.dbaas_image, container_info.dbaas_image_href = result

    def test_find_flavor(self):
        result = dbaas.find_flavor_and_self_href(flavor_id=1)
        container_info.dbaas_flavor, container_info.dbaas_flavor_href = result

    def test_create_container_name(self):
        container_info.name = "TEST_FAIL_" + str(datetime.now())


@test(depends_on_classes=[Setup], groups=[GROUP])
class CreateContainer(unittest.TestCase):

    def test_create(self):
        global dbaas
        # give the services some time to start up

        databases = []
        databases.append({"name": "firstdb", "character_set": "latin2",
                          "collate": "latin2_general_ci"})
        container_info.volume = {'size': 1}

        container_info.initial_result = dbaas.dbcontainers.create(
                                            container_info.name,
                                            container_info.dbaas_flavor_href,
                                            container_info.volume,
                                            databases)
        result = container_info.initial_result
        container_info.id = result.id
        self.assertEqual(result.status, _dbaas_mapping[power_state.BUILDING])

@test(depends_on_classes=[CreateContainer], groups=[GROUP])
class VerifyComputeInstanceRunning(unittest.TestCase):
    """
        Wait for the compute instance to begin.

        Careful- if you set the timeout too low, the compute manager will FAIL
        the container before this test even begins and this test will fail!
        
    """

    @time_out(60 * 2)
    def test_container_created(self):
        while True:
            status, err = process("sudo vzctl status %s | awk '{print $5}'"
                                  % str(container_info.id))

            if not string_in_list(status, ["running"]):
                time.sleep(5)
            else:
                self.assertEqual("running", status.strip())
                break


    @time_out(60 * 10)
    def test_get_init_pid(self):
        while True:
            out, err = process("pstree -ap | grep init | cut -d',' -f2 | vzpid - | grep %s | awk '{print $1}'"
                                % str(container_info.id))
            container_info.pid = out.strip()
            if not container_info.pid:
                time.sleep(10)
            else:
                break

    def test_guest_status_db_building(self):
        result = dbapi.guest_status_get(container_info.id)
        self.assertEqual(result.state, power_state.BUILDING)

    def test_guest_started_get_container(self):
        result = dbaas.dbcontainers.get(container_info.id)
        self.assertEqual(_dbaas_mapping[power_state.BUILDING], result.status)


@test(depends_on_classes=[VerifyComputeInstanceRunning], groups=[GROUP])
class VerifyManagerAbortsInstanceWhenInstallFails(unittest.TestCase):

    def setUp(self):
        self.db = utils.import_object(FLAGS.db_driver)

    def _assert_status_failure(self, result):
        """Checks if status==FAILED, plus asserts REST API is in sync."""
        if result[0].state == power_state.BUILDING:
            self.assertTrue(
                result[1].status == _dbaas_mapping[power_state.BUILDING] or
                result[1].status == _dbaas_mapping[power_state.FAILED],
                "Result status from API should only be BUILDING or FAILED"
                " at this point but was %s" % result[1].status)
            return False
        else:
            # After building the only valid state is FAILED (because
            # we've destroyed the container).
            self.assertEqual(result[0].state, power_state.FAILED)
            # Make sure the REST API agrees.
            self.assertEqual(result[1].status,
                             _dbaas_mapping[power_state.FAILED])
            return True

    def _get_compute_instance_state(self):
        return self.db.instance_get(context.get_admin_context(),
                                    container_info.id).state

    @staticmethod
    def _get_status_tuple():
        """Grabs the db guest status and the API instance status."""
        return (dbapi.guest_status_get(container_info.id),
                dbaas.dbcontainers.get(container_info.id))

    def test_destroy_guest_and_wait_for_failure(self):
        """Make sure the Reddwarf Compute Manager FAILS a timed-out guest."""

        # Utterly destroy the guest install.
        process("sudo rm -rf /vz/private/%s/bin" % str(container_info.id))

        # Make sure that before the timeout expires the guest state in the
        # internal API and the REST API dbcontainer status is set to FAIL.
        utils.poll_until(self._get_status_tuple, self._assert_status_failure,
                         sleep_time=1,
                         time_out=FLAGS.reddwarf_guest_initialize_time_out)

        # At this point there is a tiny chance the compute API will spend a
        # little bit of time trying to suspend the instance. We need it to
        # because, while in this case we know the guest is dead, in the real
        # world where this might happen for less-predictable reasons we want
        # to make sure the misbehaving or just slow Nova-Guest daemon doesn't
        # change its status to something besides FAILED before the container is
        # shut-off. So we have to make sure that the container turns off, and
        # the manager sets the guest state to FAILED afterwards.
        utils.poll_until(self._get_compute_instance_state,
                         lambda state : state in VALID_ABORT_STATES,
                         sleep_time=1,
                         time_out=FLAGS.reddwarf_instance_suspend_time_out)

        #TODO(tim.simpson): It'd be really cool if we could somehow coax the
        #                   guest to repeatedly setting its state in the db to
        #                   something besides failed, so we could assert that
        #                   no matter what after it was suspended it was set
        #                   to such.  Although maybe that's overkill.
        self._assert_status_failure(self._get_status_tuple())
