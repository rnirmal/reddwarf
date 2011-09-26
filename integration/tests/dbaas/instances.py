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

GROUP="dbaas.guest"
GROUP_START="dbaas.guest.initialize"
GROUP_TEST="dbaas.guest.test"
GROUP_STOP="dbaas.guest.shutdown"


from datetime import datetime
from nose.plugins.skip import SkipTest
from novaclient.exceptions import ClientException
from novaclient.exceptions import NotFound
from nose.tools import assert_true
from novaclient.exceptions import ClientException
from novaclient.exceptions import NotFound
from nova import context
from nova import db
from nova import utils
from reddwarf.api.instances import _dbaas_mapping
from reddwarf.api.instances import FLAGS as dbaas_FLAGS
from nova.compute import power_state
from reddwarf.db import api as dbapi

from proboscis.decorators import expect_exception
from proboscis.decorators import time_out
from proboscis import before_class
from proboscis import test
from proboscis.asserts import assert_equal
from proboscis.asserts import assert_not_equal
from proboscis.asserts import assert_true


from tests.util import test_config
from tests.util import check_database
from tests.util import create_dns_entry
from tests.util import create_test_client
from tests.util import process
from tests.util.users import Requirements
from tests.util import string_in_list

try:
    import rsdns
except Exception:
    rsdns = None


class InstanceTestInfo(object):
    """Stores new instance information used by dependent tests."""

    def __init__(self):
        self.dbaas = None  # The rich client instance used by these tests.
        self.dbaas_flavor = None # The flavor object of the instance.
        self.dbaas_flavor_href = None  # The flavor of the instance.
        self.dbaas_image = None  # The image used to create the instance.
        self.dbaas_image_href = None  # The link of the image.
        self.id = None  # The ID of the instance in the database.
        self.initial_result = None # The initial result from the create call.
        self.user_ip = None  # The IP address of the instance, given to user.
        self.infra_ip = None # The infrastructure network IP address.
        self.result = None  # The instance info returned by the API
        self.name = None  # Test name, generated each test run.
        self.pid = None # The process ID of the instance.
        self.user = None  # The user instance who owns the instance.
        self.volume = None # The volume the instance will have.
        self.storage = None # The storage device info for the volumes.
        self.databases = None # The databases created on the instance.

    def check_database(self, dbname):
        return check_database(self.id, dbname)

    def expected_dns_entry(self):
        """Returns expected DNS entry for this instance.

        :rtype: Instance of :class:`DnsEntry`.

        """
        return create_dns_entry(instance_info.user.auth_user,
                                instance_info.id)


# The two variables are used below by tests which depend on an instance
# existing.
instance_info = InstanceTestInfo()
dbaas = None  # Rich client used throughout this test.


# This is like a cheat code which allows the tests to skip creating a new
# instance and use an old one.
def existing_instance():
    return os.environ.get("TESTS_USE_INSTANCE_ID", None)


@property
def create_new_instance():
    return existing_instance() is None


@test(groups=[GROUP, GROUP_START, 'dbaas.setup'], depends_on_groups=["services.initialize"])
class Setup(object):
    """Makes sure the client can hit the ReST service.

    This test also uses the API to find the image and flavor to use.

    """

    @before_class
    def setUp(self):
        """Sets up the client."""
        global dbaas
        instance_info.user = test_config.users.find_user(Requirements(is_admin=True))
        dbaas = create_test_client(instance_info.user)

    @test
    def auth_token(self):
        """Make sure Auth token is correct and config is set properly."""
        print("Auth Token: %s" % dbaas.client.auth_token)
        print("Service URL: %s" % dbaas.client.management_url)
        assert_not_equal(dbaas.client.auth_token, None)
        assert_equal(dbaas.client.management_url, test_config.dbaas_url)

    @test
    def find_image(self):
        result = dbaas.find_image_and_self_href(test_config.dbaas_image)
        instance_info.dbaas_image, instance_info.dbaas_image_href = result

    @test
    def test_find_flavor(self):
        result = dbaas.find_flavor_and_self_href(flavor_id=2)
        instance_info.dbaas_flavor, instance_info.dbaas_flavor_href = result

    @test
    def create_instance_name(self):
        id = existing_instance()
        if id is None:
            instance_info.name = "TEST_" + str(datetime.now())
        else:
            instance_info.name = dbaas.instances.get(id).name

    @test
    def test_get_versions(self):
        result = dbaas.versions.index()
        print("Get version result :  %r" % result)
        print("Get version.__dict__ result :  %r" % result.__dict__)
        assert_equal("CURRENT", result.status)
        assert_equal("v1.0", result.id)


@test(depends_on_classes=[Setup], depends_on_groups=['dbaas.setup'],
      groups=[GROUP, GROUP_START, 'dbaas.mgmt.hosts'],
      enabled=create_new_instance)
class InstanceHostCheck(unittest.TestCase):
    """Class to run tests after Setup"""

    def test_empty_index_host_list(self):
        host_index_result = dbaas.hosts.index()
        self.assertNotEqual(host_index_result, None,
                            "list hosts call should not be empty")
        print("result : %r" % str(host_index_result))
        self.assertTrue(len(host_index_result) > 0,
                        "list hosts length should not be empty")
        print("test_index_host_list result: %r" % host_index_result[0])
        print("instance count for host : %r" % host_index_result[0].instanceCount)
        self.assertEquals(int(host_index_result[0].instanceCount), 0,
                          "instance count of 'host' should have 0 running instances")
        print("test_index_host_list result instance_count: %r" %
              host_index_result[0].instanceCount)
        self.assertEquals(len(host_index_result), 1,
                          "The host result list is expected to be of length 1")
        for host in list(enumerate(host_index_result, start=1)):
            print("%r host: %r" % (host[0], host[1]))
            instance_info.host = host[1]

    def test_empty_index_host_list_single(self):
        print("instance_info.host : %r" % instance_info.host)
        host_index_result = dbaas.hosts.get(instance_info.host)
        self.assertNotEqual(host_index_result, None,
                            "list hosts should not be empty")
        print("test_index_host_list_single result: %r" %
              host_index_result.__dict__)
        self.assertTrue(host_index_result.percentUsed == 0,
                        "percentUsed should be 0 : %r" % host_index_result.percentUsed)
        self.assertTrue(host_index_result.totalRAM,
                        "totalRAM should exist > 0 : %r" % host_index_result.totalRAM)
        self.assertTrue(host_index_result.usedRAM == 0,
                        "usedRAM should be 0 : %r" % host_index_result.usedRAM)
        self.assertTrue(instance_info.name
                        not in [dbc.name for dbc
                                in host_index_result.instances])
        instance_info.host_info = host_index_result
        for index, instance in enumerate(host_index_result.instances, start=1):
            print("%r instance: %r" % (index, instance))

    @expect_exception(NotFound)
    def test_host_not_found(self):
        instance_info.myresult = dbaas.hosts.get('host@$%3dne')

    def test_storage_on_host(self):
        storage = dbaas.storage.index()
        print("storage : %r" % storage)
        self.assertTrue(hasattr(storage, 'name'))
        self.assertTrue(hasattr(storage, 'availablesize'))
        self.assertTrue(hasattr(storage, 'totalsize'))
        print("storage.name : %r" % storage.name)
        print("storage.availablesize : %r" % storage.availablesize)
        print("storage.totalsize : %r" % storage.totalsize)
        instance_info.storage = storage

    @expect_exception(NotFound)
    def test_no_details_bogus_account(self):
        dbaas.accounts.show('asd#4#@fasdf')

    def test_no_details_empty_account(self):
        account_info = dbaas.accounts.show(instance_info.user.auth_user)
        self.assertEqual(0, len(account_info.hosts))


@test(depends_on_classes=[InstanceHostCheck], groups=[GROUP, GROUP_START])
class CreateInstance(unittest.TestCase):
    """Test to create a Database Instance

    If the call returns without raising an exception this test passes.

    """

    def test_before_instances_are_started(self):
        # give the services some time to start up
        time.sleep(2)

    @expect_exception(ClientException)
    def test_instance_size_too_big(self):
        too_big = dbaas_FLAGS.reddwarf_max_accepted_volume_size
        dbaas.instances.create('way_too_large',
                                  instance_info.dbaas_flavor_href,
                                  {'size': too_big + 1}, [])

    def test_create(self):
        databases = []
        databases.append({"name": "firstdb", "character_set": "latin2",
                          "collate": "latin2_general_ci"})
        databases.append({"name": "db2"})
        instance_info.databases = databases
        instance_info.volume = {'size': 2}

        if create_new_instance:
            instance_info.initial_result = dbaas.instances.create(
                                               instance_info.name,
                                               instance_info.dbaas_flavor_href,
                                               instance_info.volume,
                                               databases)
        else:
            id = existing_instance()
            instance_info.initial_result = dbaas.instances.get(id)
        
        result = instance_info.initial_result
        instance_info.id = result.id

        if create_new_instance:
            self.assertEqual(result.status,
                             _dbaas_mapping[power_state.BUILDING])
        
        # checks to be sure these are not found in the result
        for attr in ['hostId', 'imageRef', 'metadata', 'adminPass', 'uuid',
                     'volumes', 'addresses']:
            self.assertFalse(hasattr(result, attr),
                            "Create response should not contain %r." % attr)
        # checks to be sure these are found in the result
        for attr in ['flavor', 'id', 'name', 'status', 'links', 'volume']:
            self.assertTrue(hasattr(result, attr),
                            "Create response should contain %r attribute." % attr)

    def test_security_groups_created(self):
        if not db.security_group_exists(context.get_admin_context(), "dbaas", "tcp_3306"):
            self.assertFalse(True, "Security groups did not get created")


@test(depends_on_classes=[CreateInstance], groups=[GROUP, GROUP_START, 'dbaas.mgmt.hosts_post_install'])
class AccountMgmtData(unittest.TestCase):
    def test_account_details_available(self):
        account_info = dbaas.accounts.show(instance_info.user.auth_user)
        self.assertNotEqual(0, len(account_info.hosts))
        # Now check the results.
        self.assertEqual(account_info.name, instance_info.user.auth_user)
        # Instances: Here we know we've only created one host.
        self.assertEqual(1, len(account_info.hosts))
        self.assertEqual(1, len(account_info.hosts[0]['instances']))
        # We know that the host should contain only one instance.
        instance = account_info.hosts[0]['instances'][0]['instance']
        print("instances in account: %s" % instance)
        self.assertEqual(instance['id'], instance_info.id)
        self.assertEqual(instance['name'], instance_info.name)


@test(depends_on_classes=[CreateInstance], groups=[GROUP, GROUP_START],
      enabled=create_new_instance)
class WaitForGuestInstallationToFinish(unittest.TestCase):
    """
        Wait until the Guest is finished installing.  It takes quite a while...
    """

    @time_out(60 * 8)
    def test_instance_created(self):
        #/vz/private/1/var/log/nova/nova-guest.log
        while True:
            guest_status = dbapi.guest_status_get(instance_info.id)
            if guest_status.state != power_state.RUNNING:
                result = dbaas.instances.get(instance_info.id)
                # I think there's a small race condition which can occur
                # between the time you grab "guest_status" and "result," so
                # RUNNING is allowed in addition to BUILDING.
                self.assertTrue(
                    result.status == _dbaas_mapping[power_state.BUILDING] or
                    result.status == _dbaas_mapping[power_state.RUNNING],
                    "Result status was %s" % result.status)
                time.sleep(5)
            else:
                break

    def test_instance_wait_for_initialize_guest_to_exit_polling(self):
        def compute_manager_finished():
            return util.check_logs_for_message("INFO reddwarf.compute.manager [-] Guest is now running on instance %s"
                                        % str(instance_info.id))
        utils.poll_until(compute_manager_finished, sleep_time=2, time_out=60)

@test(depends_on_classes=[WaitForGuestInstallationToFinish],
      groups=[GROUP, GROUP_START], enabled=create_new_instance)
class VerifyGuestStarted(unittest.TestCase):
    """
        Test to verify the guest instance is started and we can get the init
        process pid.
    """

    def test_instance_created(self):
        def check_status_of_instance():
            status, err = process("sudo vzctl status %s | awk '{print $5}'"
                                  % str(instance_info.id))
            if string_in_list(status, ["running"]):
                self.assertEqual("running", status.strip())
                return True
            else:
                return False
        utils.poll_until(check_status_of_instance, sleep_time=5, time_out=60*8)

    def test_get_init_pid(self):
        def get_the_pid():
            out, err = process("pgrep init | vzpid - | awk '/%s/{print $1}'"
                                % str(instance_info.id))
            instance_info.pid = out.strip()
            return len(instance_info.pid) > 0
        utils.poll_until(get_the_pid, sleep_time=10, time_out=60*10)


@test(depends_on_classes=[WaitForGuestInstallationToFinish],
      groups=[GROUP, GROUP_START], enabled=create_new_instance)
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
                                            % instance_info.pid)
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
            result = dbapi.guest_status_get(instance_info.id)
            state = result.state
        time.sleep(1)
        self.assertEqual(state, power_state.RUNNING)


    def test_guest_status_get_instance(self):
        result = dbaas.instances.get(instance_info.id)
        self.assertEqual(_dbaas_mapping[power_state.RUNNING], result.status)


@test(depends_on_classes=[CreateInstance], groups=[GROUP, GROUP_START, "nova.volumes.instance"])
class TestVolume(unittest.TestCase):
    """Make sure the volume is attached to instance correctly."""

    def test_db_should_have_instance_to_volume_association(self):
        """The compute manager should associate a volume to the instance."""
        volumes = db.volume_get_all_by_instance(context.get_admin_context(), 
                                                instance_info.id)
        self.assertEqual(1, len(volumes))
        description = "Volume ID: %s assigned to Instance: %s" \
                        % (volumes[0]['id'], instance_info.id)
        self.assertEqual(description, volumes[0]['display_description'])


@test(depends_on_classes=[WaitForGuestInstallationToFinish], groups=[GROUP, GROUP_START, "dbaas.listing"])
class TestInstanceListing(unittest.TestCase):
    """ Test the listing of the instance information """

    def test_detail_list(self):
        instances = dbaas.instances.details()
        for instance in instances:
            self._detail_instances_exist(instance)
            self._instances_attributes_should_not_exist(instance)

    def test_index_list(self):
        instances = dbaas.instances.index()
        for instance in instances:
            self._index_instances_exist(instance)
            self._index_instances_attrs_should_not_exist(instance)
            self._instances_attributes_should_not_exist(instance)

    def test_get_instance(self):
        instance = dbaas.instances.get(instance_info.id)
        self._assert_instances_exist(instance)
        self._instances_attributes_should_not_exist(instance)

    def test_get_instance_status(self):
        result = dbaas.instances.get(instance_info.id)
        self.assertEqual(_dbaas_mapping[power_state.RUNNING], result.status)

    def test_get_legacy_status(self):
        result = dbaas.instances.get(instance_info.id)
        self.assertTrue(result is not None)

    def test_get_legacy_status_notfound(self):
        self.assertRaises(NotFound, dbaas.instances.get, -2)

    # Calling has_key on the instance triggers a lazy load.
    # We don't want that here, so the next two methods use the _info dict.

    def _check_attr_in_instances(self, instance, attrs):
        for attr in attrs:
            msg = "Missing attribute %r" % attr
            self.assertTrue(instance._info.has_key(attr), msg)

    def _check_should_not_show_attr_in_instances(self, instance, attrs):
        for attr in attrs:
            msg = "Attribute %r should not be returned" % attr
            self.assertFalse(instance._info.has_key(attr), msg)

    def _detail_instances_exist(self, instance):
        attrs = ['status', 'name', 'links', 'id', 'volume']
        self._check_attr_in_instances(instance, attrs)

    def _instances_attributes_should_not_exist(self, instance):
        attrs = ['hostId', 'imageRef', 'metadata', 'adminPass', 'uuid',
                 'volumes', 'addresses']
        self._check_should_not_show_attr_in_instances(instance, attrs)

    def _index_instances_exist(self, instance):
        attrs = ['id', 'name', 'links', 'status']
        self._check_attr_in_instances(instance, attrs)

    def _index_instances_attrs_should_not_exist(self, instance):
        attrs = ['flavorRef', 'rootEnabled', 'volume', 'databases']
        self._check_should_not_show_attr_in_instances(instance, attrs)

    def test_volume_found(self):
        instance = dbaas.instances.get(instance_info.id)
        self.assertEqual(instance_info.volume['size'], instance.volume['size'])

    def _assert_instances_exist(self, instance):
        self.assertEqual(instance_info.id, instance.id)
        attrs = ['name', 'links', 'id', 'flavor', 'status', 'volume', 'databases']
        self._check_attr_in_instances(instance, attrs)
        print("instance_info.databases : %r" % instance.databases)
        print("instance_info.databases : %r" % instance_info.databases)
        self.assertEqual(len(instance_info.databases), len(instance.databases))
        for db in instance.databases:
            print("db : %r" % db)            
            self.assertTrue(db.has_key('character_set'))
            print("db['charset'] : %r" % db['character_set'])
            self.assertTrue(db.has_key('name'))
            print("db['name'] : %r" % db['name'])
            self.assertTrue(db.has_key('collate'))
            print("db['collate'] : %r" % db['collate'])
        dns_entry = instance_info.expected_dns_entry()
        if dns_entry:
            self.assertEqual(dns_entry.name, instance.hostname)


@test(depends_on_classes=[CreateInstance], groups=[GROUP, "dbaas.mgmt.listing"])
class MgmtHostCheck(unittest.TestCase):
    def test_index_host_list(self):
        myresult = dbaas.hosts.index()
        self.assertNotEqual(myresult, None,
                            "list hosts should not be empty")
        self.assertTrue(len(myresult) > 0,
                        "list hosts should not be empty")
        print("test_index_host_list result: %s" % str(myresult))
        print("test_index_host_list result instance_count: %d" %
              myresult[0].instanceCount)
        self.assertEquals(myresult[0].instanceCount, 1,
                          "instance count of 'host' should have 1 running instances")
        self.assertEquals(len(myresult), 1,
                          "The result list is expected to be of length 1")
        for index, host in enumerate(myresult, start=1):
            print("%d host: %s" % (index, host))
            instance_info.host = host

    def test_index_host_list_single(self):
        myresult = dbaas.hosts.get(instance_info.host)
        self.assertNotEqual(myresult, None,
                            "list hosts should not be empty")
        print("test_index_host_list_single result: %s" %
              str(myresult))
        self.assertTrue(len(myresult.instances) > 0,
                        "instance list on the host should not be empty")
        self.assertTrue(myresult.totalRAM == instance_info.host_info.totalRAM,
                        "totalRAM should be the same as before : %r == %r" %
                        (myresult.totalRAM, instance_info.host_info.totalRAM))
        diff = instance_info.host_info.usedRAM + instance_info.dbaas_flavor.ram
        self.assertTrue(myresult.usedRAM == diff,
                        "usedRAM should be : %r == %r" %
                        (myresult.usedRAM, diff))
        calc = round(1.0 * myresult.usedRAM / myresult.totalRAM * 100)
        self.assertTrue(myresult.percentUsed == calc,
                        "percentUsed should be : %r == %r" %
                        (myresult.percentUsed, calc))
        print("test_index_host_list_single result instances: %s" %
              str(myresult.instances))
        for index, instance in enumerate(myresult.instances, start=1):
            print("%d instance: %s" % (index, instance))
            self.assertEquals(['id', 'state'], sorted(instance.keys()))

    def test_storage_on_host(self):
        storage = dbaas.storage.index()
        print("storage : %r" % storage)
        self.assertTrue(hasattr(storage, 'name'))
        self.assertTrue(hasattr(storage, 'availablesize'))
        self.assertTrue(hasattr(storage, 'totalsize'))
        self.assertTrue(hasattr(storage, 'type'))
        print("storage : %r" % storage.__dict__)
        print("instance_info.dbaas_flavor : %r" % instance_info.dbaas_flavor.__dict__)
        print("instance_info.storage : %r" % instance_info.storage.__dict__)
        self.assertEquals(storage.name, instance_info.storage.name)
        self.assertEquals(storage.totalsize, instance_info.storage.totalsize)
        self.assertEquals(storage.type, instance_info.storage.type)
        avail = instance_info.storage.availablesize - instance_info.volume['size']
        self.assertEquals(storage.availablesize, avail)

    def test_account_details_available(self):
        account_info = dbaas.accounts.show(instance_info.user.auth_user)
        self.assertNotEqual(0, len(account_info.hosts))

@test(depends_on_groups=[GROUP_TEST], groups=[GROUP, GROUP_STOP])
class DeleteInstance(unittest.TestCase):
    """ Delete the created instance """

    @time_out(3 * 60)
    def test_delete(self):
        global dbaas
        if not hasattr(instance_info, "initial_result"):
            raise SkipTest("Instance was never created, skipping test...")
        dbaas.instances.delete(instance_info.id)

        attempts = 0
        try:
            time.sleep(1)
            result = True
            while result is not None:
                attempts += 1
                result = dbaas.instances.get(instance_info.id)
                self.assertEqual(_dbaas_mapping[power_state.SHUTDOWN], result.status)
        except NotFound:
            pass
        except Exception as ex:
            self.fail("A failure occured when trying to GET instance %s"
                      " for the %d time: %s" %
                      (str(instance_info.id), attempts, str(ex)))

    #TODO: make sure that the actual instance, volume, guest status, and DNS
    #      entries are deleted.

@test(depends_on_classes=[DeleteInstance], groups=[GROUP, GROUP_STOP])
class InstanceHostCheck2(InstanceHostCheck):
    """Class to run tests after delete"""

    @expect_exception(Exception)
    def test_host_not_found(self):
        instance_info.myresult = dbaas.hosts.get('host-dne')

    @expect_exception(Exception)
    def test_host_not_found(self):
        instance_info.myresult = dbaas.hosts.get('host@$%3dne')

    def test_no_details_empty_account(self):
        account_info = dbaas.accounts.show(instance_info.user.auth_user)
        # Instances were created and then deleted or crashed.
        # In the process, one host was created.
        self.assertEqual(1, len(account_info.hosts))


@test(depends_on_classes=[CreateInstance, VerifyGuestStarted,
    WaitForGuestInstallationToFinish], groups=[GROUP, GROUP_START])
def management_callback():
    global mgmt_details
    mgmt_details = dbaas.management.show(instance_info.id)


@test(depends_on=[management_callback], groups=[GROUP])
class VerifyInstanceMgmtInfo(unittest.TestCase):

    def _assert_key(self, k, expected):
        v = getattr(mgmt_details, k)
        err = "Key %r does not match expected value of %r (was %r)." % (k, expected, v)
        self.assertEqual(str(v), str(expected), err)

    def test_id_matches(self):
        self._assert_key('id', instance_info.id)

    def test_bogus_instance_mgmt_data(self):
        # Make sure that a management call to a bogus API 500s.
        # The client reshapes the exception into just an OpenStackException.
        #self.assertRaises(nova.exception.InstanceNotFound, dbaas.management.show, -1)
        self.assertRaises(NotFound, dbaas.management.show, -1)
    
    def test_mgmt_data(self):
        # Test that the management API returns all the values we expect it to.
        info = instance_info
        ir = info.initial_result
        cid = ir.id
        volumes = db.volume_get_all_by_instance(context.get_admin_context(), cid)
        self.assertEqual(len(volumes), 1)
        volume = volumes[0]

        expected = {
            'id': str(ir.id),
            'name': ir.name,
            'account_id': info.user.auth_user,
            # TODO(hub-cap): fix this since its a flavor object now
            #'flavorRef': info.dbaas_flavor_href,
            'databases': [{
                'name': 'db2',
                'character_set': 'utf8',
                'collate': 'utf8_general_ci',},{
                'name': 'firstdb',
                'character_set': 'latin2',
                'collate': 'latin2_general_ci',
                }],
            'users': [], # TODO(ed-) Surely I can't guarantee this.
            'volume': {
                'id': volume.id,
                'name': volume.display_name,
                'size': volume.size,
                'description': volume.display_description,
                },
            }

        expected_entry = info.expected_dns_entry()
        if expected_entry:
            expected['hostname'] = expected_entry.name

        self.assertTrue(mgmt_details is not None)
        failures = []
        for (k,v) in expected.items():
            self.assertTrue(hasattr(mgmt_details, k), "Attr %r is missing." % k)
            self.assertEqual(getattr(mgmt_details, k), v,
                "Attr %r expected to be %r but was %r." %
                (k, v, getattr(mgmt_details, k)))

