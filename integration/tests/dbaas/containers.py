import gettext
import os
import json
import re
import sys
import time
import unittest
from tests import util

GROUP="dbaas.guest"
GROUP_START="dbaas.guest.initialize"
GROUP_TEST="dbaas.guest.test"
GROUP_STOP="dbaas.guest.shutdown"


from datetime import datetime
from nose.plugins.skip import SkipTest
from novaclient.exceptions import NotFound
from nova import context
from nova import db
from nova import exception
from nova.api.platform.dbaas.dbcontainers import _dbaas_mapping
from nova.compute import power_state
from reddwarf.db import api as dbapi

from reddwarfclient import Dbaas
from tests.util import test_config
from proboscis.decorators import time_out
from proboscis import test
from tests.util import check_database
from tests.util import create_dns_entry
from tests.util import process
from tests.util.users import Requirements
from tests.util import string_in_list


try:
    import rsdns
except Exception:
    rsdns = None


class ContainerTestInfo(object):
    """Stores new container information used by dependent tests."""

    def __init__(self):
        self.dbaas = None  # The rich client instance used by these tests.
        self.dbaas_flavor_href = None  # The flavor of the container.
        self.dbaas_image_href = None  # The image used to create the container.
        self.id = None  # The ID of the instance in the database.
        self.ip = None  # The IP of the instance.
        self.name = None  # Test name, generated each test run.
        self.pid = None # The process ID of the instance.
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

@test(groups=[GROUP, GROUP_START], depends_on_groups=["services.initialize"])
class Setup(unittest.TestCase):
    """Makes sure the client can hit the ReST service.

    This test also uses the API to find the image and flavor to use.

    """

    def setUp(self):
        """Sets up the client."""
        global dbaas
        container_info.user = test_config.users.find_user(Requirements(is_admin=True))
        dbaas = util.create_dbaas_client(container_info.user)

    def test_find_image(self):
        self.assertNotEqual(None, test_config.dbaas_image)
        images = dbaas.images.list()
        for image in images:
            if int(image.id) == test_config.dbaas_image:
                container_info.dbaas_image = image
                for link in container_info.dbaas_image.links:
                    if link['rel'] == "self":
                        container_info.dbaas_image_href = link['href']
                if not container_info.dbaas_image_href:
                    raise Exception("Found image with ID %s, but it had no " 
                                    "self href!" % str(test_config.dbaas_image))
        self.assertNotEqual(None, container_info.dbaas_image)

    def test_find_flavor(self):
        self.assertNotEqual(None, test_config.dbaas_image)
        flavors = dbaas.flavors.list()
        for flavor in flavors:
            if int(flavor.id) == 1:
                container_info.dbaas_flavor = flavor
                for link in container_info.dbaas_flavor.links:
                    if link['rel'] == "self":
                        container_info.dbaas_flavor_href = link['href']
                if not container_info.dbaas_flavor_href:
                    raise Exception("Found flavor with ID %s, but it had no "
                                    "self href!" % str(1))
        self.assertNotEqual(None, container_info.dbaas_flavor)

    def test_create_container_name(self):
        container_info.name = "TEST_" + str(datetime.now())

@test(depends_on_classes=[Setup], groups=[GROUP, GROUP_START])
class CreateContainer(unittest.TestCase):
    """Test to create a Database Container

    If the call returns without raising an exception this test passes.

    """

    def test_create(self):
        global dbaas
        # give the services some time to start up
        time.sleep(2)

        databases = []
        databases.append({"name": "firstdb", "charset": "latin2",
                          "collate": "latin2_general_ci"})

        container_info.result = dbaas.dbcontainers.create(
                                            container_info.name,
                                            container_info.dbaas_flavor_href,
                                            databases)
        container_info.id = container_info.result.id
        
        # checks to be sure these are not found in the result
        result_dict = container_info.result.__dict__
        for attr in ["hostId","imageRef","metadata","adminPass"]:
            self.assertTrue(result_dict.get(attr) == None,
                            "Create response should not contain %s = %s" %
                            (attr, result_dict.get(attr)))
        # checks to be sure these are found in the result
        for attr in ["flavorRef","id","name","status","addresses","links"]:
            self.assertTrue(result_dict.get(attr) != None,
                            "Create response should contain %s = %s attribute." %
                            (attr, result_dict.get(attr)))

    def test_get_container(self):
        container_info.myresult = dbaas.dbcontainers.get(container_info.id).__dict__
        self.assertEquals(_dbaas_mapping[power_state.BUILDING], container_info.myresult['status'])

    def test_security_groups_created(self):
        if not db.security_group_exists(context.get_admin_context(), "dbaas", "tcp_3306"):
            self.assertFalse(True, "Security groups did not get created")


@test(depends_on_classes=[CreateContainer], groups=[GROUP, GROUP_START])
class VerifyGuestStarted(unittest.TestCase):
    """
        Test to verify the guest container is started and we can get the init
        process pid.
    """

    @time_out(60 * 8)
    def test_container_created(self):
        while True:
            status, err = process("sudo vzctl status %s | awk '{print $5}'"
                                  % str(container_info.id))

            if not string_in_list(status, ["running"]):
                time.sleep(5)
            else:
                self.assertEquals("running", status.strip())
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
        container_info.myresult = dbaas.dbcontainers.get(container_info.id).__dict__
        self.assertEquals(_dbaas_mapping[power_state.BUILDING], container_info.myresult['status'])


@test(depends_on_classes=[VerifyGuestStarted], groups=[GROUP, GROUP_START])
class WaitForGuestInstallationToFinish(unittest.TestCase):
    """
        Wait until the Guest is finished installing.  It takes quite a while...
    """

    @time_out(60 * 8)
    def test_container_created(self):
        #/vz/private/1/var/log/nova/nova-guest.log
        while True:
            status, err = process(
                """cat /vz/private/%s/var/log/nova/nova-guest.log | grep "Dbaas" """
                % str(container_info.id))
            if not string_in_list(status, ["Dbaas preparation complete."]):
                time.sleep(5)
            else:
                break


@test(depends_on_classes=[WaitForGuestInstallationToFinish], groups=[GROUP, GROUP_START])
class TestGuestProcess(unittest.TestCase):
    """
        Test that the guest process is started with all the right parameters
    """

    @time_out(60 * 10)
    def test_guest_process(self):
        init_proc = re.compile("[\w\W\|\-\s\d,]*nova-guest --flagfile=/etc/nova/nova.conf nova[\W\w\s]*")
        guest_proc = re.compile("[\w\W\|\-\s]*/usr/bin/nova-guest --flagfile=/etc/nova/nova.conf[\W\w\s]*")
        apt = re.compile("[\w\W\|\-\s]*apt-get[\w\W\|\-\s]*")
        while True:
            guest_process, err = process("pstree -ap %s | grep nova-guest"
                                            % container_info.pid)
            if not string_in_list(guest_process, ["nova-guest"]):
                time.sleep(10)
            else:
                if apt.match(guest_process):
                    time.sleep(10)
                else:
                    init = init_proc.match(guest_process)
                    guest = guest_proc.match(guest_process)
                    if init and guest:
                        self.assertTrue(True, init.group())
                    else:
                        self.assertFalse(False, guest_process)
                    break

    @time_out(130)
    def test_guest_status_db_running(self):
        state = power_state.BUILDING
        while state != power_state.RUNNING:
            time.sleep(10)
            result = dbapi.guest_status_get(container_info.id)
            state = result.state
        time.sleep(1)
        self.assertEqual(state, power_state.RUNNING)


    def test_guest_status_get_container(self):
        container_info.myresult = dbaas.dbcontainers.get(container_info.id).__dict__
        self.assertEquals(_dbaas_mapping[power_state.RUNNING], container_info.myresult['status'])


@test(depends_on_classes=[Setup], groups=[GROUP, GROUP_START, "dbaas.listing"])
class TestContainListing(unittest.TestCase):
    """ Test the listing of the container information """
    
    def test_detail_list(self):
        container_info.myresult = dbaas.dbcontainers.details()
        self.assertTrue(self._detail_dbcontainers_exist())

    def test_index_list(self):
        container_info.myresult = dbaas.dbcontainers.index()
        self.assertTrue(self._index_dbcontainers_exist())

    def test_get_container(self):
        container_info.myresult = dbaas.dbcontainers.get(container_info.id)
        self._assert_dbcontainers_exist()

    def test_get_container_status(self):
        container_info.myresult = dbaas.dbcontainers.get(container_info.id).__dict__
        self.assertEquals(_dbaas_mapping[power_state.RUNNING], container_info.myresult['status'])

    def test_get_legacy_status(self):
        container_info.myresult = dbaas.dbcontainers.get(container_info.id).__dict__
        if len(container_info.myresult)>0:
            self.assertTrue(True)
        else:
            self.assertTrue(False)

    def test_get_legacy_status_notfound(self):
        try:
            if dbaas.dbcontainers.get(-2):
                self.assertTrue(True)
            else:
                self.assertTrue(False)
        except NotFound:
            pass

    def _detail_dbcontainers_exist(self):
        for container in container_info.myresult:
            if not container.__dict__['status']:
                return False
            if not container.__dict__['id'] and container.__dict__['id'] != container_info.id:
                return False
            if not container.__dict__['name']:
                return False
            if not container.__dict__['addresses']:
                return False
            if not container.__dict__['links']:
                return False
        return True

    def _index_dbcontainers_exist(self):
        for container in container_info.myresult:
            if not container.__dict__['id'] and container.__dict__['id'] != container_info.id:
                return False
            if not container.__dict__['name']:
                return False
            if not container.__dict__['links']:
                return False
        return True

    def _assert_dbcontainers_exist(self):
        container = container_info.myresult
        self.assertEqual(container_info.id, container.id)        
        self.assertTrue(container.name is not None)
        self.assertTrue(container.links is not None)
        if rsdns:
            dns_entry = container_info.expected_dns_entry()
            self.assertEqual(dns_entry.name, container.hostname)


@test(depends_on_groups=[GROUP_TEST], groups=[GROUP, GROUP_STOP],
      never_skip=True)
class DeleteContainer(unittest.TestCase):
    """ Delete the created container """

    @time_out(6 * 60)
    def test_delete(self):
        global dbaas

        dbaas.dbcontainers.delete(container_info.result)

        try:
            time.sleep(1)
            while container_info.result:
                container_info.result = dbaas.dbcontainers.get(container_info.id)
                self.assertEquals(_dbaas_mapping[power_state.SHUTDOWN], container_info.result.__dict__['status'])
        except NotFound:
            pass
