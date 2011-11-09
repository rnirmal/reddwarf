import gettext
import os
import subprocess
import sys
import time
import re
import unittest

from sqlalchemy import create_engine
from sqlalchemy.sql.expression import text

from nova import context
from nova import db
from nova.guest.dbaas import LocalSqlClient
from novaclient.exceptions import NotFound
from reddwarfclient import Dbaas

from nose.tools import assert_equal
from nose.tools import assert_not_equal
from nose.tools import assert_true
from nose.tools import assert_false

from proboscis import before_class
from proboscis import test
from proboscis.asserts import fail
from proboscis.decorators import expect_exception
from proboscis.decorators import time_out
from tests.dbaas.instances import instance_info
from tests.dbaas.instances import GROUP_START
from tests.dbaas.instances import GROUP_TEST
from tests.util import check_database
from tests.util import get_vz_ip_for_device
from tests.util import init_engine
from tests.util import process
from tests.util import string_in_list
from tests.util import test_config
from tests.util.users import Requirements
from tests import util

dbaas = None
success_statuses = ["build", "active"]


@test(depends_on_groups=[GROUP_START])
class Setup(unittest.TestCase):
    """Creates the client."""

    def test_create_dbaas_client(self):
        """Sets up the client."""
        global dbaas
        dbaas = util.create_dbaas_client(instance_info.user)


@test(depends_on_classes=[Setup], groups=[GROUP_TEST, "dbaas.guest.ovz"])
class TestMultiNic(unittest.TestCase):
    """
        Test that the created instance has 2 nics with the specified ip
        address as allocated to it.
    """

    def setUp(self):
        instance_info.user_ip = get_vz_ip_for_device(instance_info.id,
                                                      "eth0")
        instance_info.infra_ip = get_vz_ip_for_device(instance_info.id,
                                                       "eth1")

    def test_multi_nic(self):
        """
        Multinic - Verify that nics as specified in the database are created
        in the guest
        """
        vifs = db.virtual_interface_get_by_instance(context.get_admin_context(),
                                                    instance_info.id)
        for vif in vifs:
            fixed_ip = db.fixed_ip_get_by_virtual_interface(context.get_admin_context(),
                                                            vif['id'])
            vz_ip = get_vz_ip_for_device(instance_info.id,
                                         vif['network']['bridge_interface'])
            self.assertEquals(vz_ip, fixed_ip[0]['address'])


@test(depends_on_classes=[TestMultiNic], groups=[GROUP_TEST, "dbaas.guest.mysql"])
class TestMysqlAccess(unittest.TestCase):
    """
        Test Access to the mysql server as os_admin and root
    """

    def _mysql_error_handler(self, err):
        pos_error = re.compile("ERROR 1130 \(HY000\): Host '[\w\.]*' is not allowed to connect to this MySQL server")
        pos_error1 = re.compile("ERROR 1045 \(28000\): Access denied for user '[\w]*'@'[\w\.]*' \(using password: (YES|NO)\)")
        neg_error = re.compile("ERROR 2003 \(HY000\): Can't connect to MySQL server on *")
        if pos_error.match(err) or pos_error1.match(err):
            self.assertTrue(True, err)
        elif neg_error.match(err):
            self.assertFalse(True, err)
        else:
            raise RuntimeError(err)

    @time_out(60 * 2)
    def test_mysql_admin(self):
        while True:
            mysqld, err = process("pgrep -l -P %s mysqld" % instance_info.pid)
            if not string_in_list(mysqld, ["mysqld"]):
                time.sleep(10)
            else:
                time.sleep(10)
                out, err = process("mysql -h %s -u os_admin -pasdfd-asdf234"
                                    % instance_info.user_ip)
                self._mysql_error_handler(err)
                break

    def test_mysql_root(self):
        out, err = process("mysql -h %s -u root -pdsfgnear"
                           % instance_info.user_ip)
        self._mysql_error_handler(err)

    def test_zfirst_db(self):
        if instance_info.check_database("firstdb"):
            self.assertTrue(True)
        else:
            self.assertFalse(True)


@test(depends_on_classes=[TestMysqlAccess], groups=[GROUP_TEST,
                                                    "dbaas.guest.mysql"])
class TestDatabases(unittest.TestCase):
    """
    Test the creation and deletion of additional MySQL databases
    """

    dbname = "third #?@some_-"
    dbname_urlencoded = "third%20%23%3F%40some_-"

    dbname2 = "seconddb"
    created_dbs = [dbname, dbname2]
    system_dbs = ['information_schema','mysql', 'lost+found']

    def test_create_database(self):
        databases = list()
        databases.append({"name": self.dbname, "charset": "latin2",
                          "collate": "latin2_general_ci"})
        databases.append({"name": self.dbname2})

        dbaas.databases.create(instance_info.id, databases)
        time.sleep(5)

    def test_create_database_list(self):
        databases = dbaas.databases.list(instance_info.id)
        found = False
        for db in self.created_dbs:
            for result in databases:
                if result.name == db:
                    found = True
            self.assertTrue(found, "Database '%s' not found in result" %db)
            found = False

    def test_create_database_list_system(self):
        #Databases that should not be returned in the list
        databases = dbaas.databases.list(instance_info.id)
        found = False
        for db in self.system_dbs:
            found = any(result.name == db for result in databases)
            self.assertFalse(found, "Database '%s' SHOULD NOT be found in result" %db)
            found = False
            
    @expect_exception(NotFound)
    def test_create_database_on_missing_instance(self):
        databases = [{"name": "invalid_db", "charset": "latin2",
                      "collate": "latin2_general_ci"}]
        dbaas.databases.create(-1, databases)

    @expect_exception(NotFound)
    def test_delete_database_on_missing_instance(self):
        global dbaas
        dbaas.databases.delete(-1,  self.dbname_urlencoded)

    def test_delete_database(self):
        global dbaas
        dbaas.databases.delete(instance_info.id, self.dbname_urlencoded)
        time.sleep(5)

        if not instance_info.check_database(self.dbname):
            self.assertTrue(True)
        else:
            self.assertFalse(True)


@test(depends_on_classes=[TestDatabases], groups=[GROUP_TEST, 'rootenabled',
                                                  "dbaas.guest.mysql"])
class TestUsers(object):
    """
    Test the creation and deletion of users
    """

    username = "tes!@#tuser"
    username_urlencoded = "tes%21%40%23tuser"
    password = "testpa$^%ssword"
    username1 = "anous*&^er"
    username1_urlendcoded = "anous%2A%26%5Eer"
    password1 = "anopas*?.sword"
    db1 = "firstdb"
    db2 = "seconddb"
    root_enabled_timestamp = 'Never'

    created_users = [username, username1]
    system_users = ['root', 'debian_sys_maint']

    @test()
    def test_create_users(self):
        users = list()
        users.append({"name": self.username, "password": self.password,
                      "database": self.db1})
        users.append({"name": self.username1, "password": self.password1,
                     "databases": [{"name": self.db1}, {"name": self.db2}]})

        global dbaas
        dbaas.users.create(instance_info.id, users)
        time.sleep(5)

        self.check_database_for_user(self.username, self.password,
                                    [self.db1])
        self.check_database_for_user(self.username1, self.password1,
                                    [self.db1, self.db2])

    @test(depends_on=[test_create_users])
    def test_create_users_list(self):
        #tests for users that should be listed
        users = dbaas.users.list(instance_info.id)
        found = False
        for user in self.created_users:
            for result in users:
                if user == result.name:
                    found = True
            assert_true(found, "User '%s' not found in result" %user)
            found = False

    @test(depends_on=[test_create_users_list])
    def test_create_users_list_system(self):
        #tests for users that should not be listed
        users = dbaas.users.list(instance_info.id)
        found = False
        for user in self.system_users:
            found = any(result.name == user for result in users)
            assert_false(found, "User '%s' SHOULD NOT BE found in result" %user)
            found = False

    @test(depends_on=[test_create_users_list])
    def test_delete_users(self):
        global dbaas
        dbaas.users.delete(instance_info.id, self.username_urlencoded)
        dbaas.users.delete(instance_info.id, self.username1_urlendcoded)
        time.sleep(5)

        self._check_connection(self.username, self.password)
        self._check_connection(self.username1, self.password1)

    def check_database_for_user(self, user, password, dbs):
        cmd = "sudo mysql    -h %s -u '%s' -p'%s' -e 'show databases;'" \
              % (instance_info.user_ip, user, password)
        print("Running cmd: %s" % cmd)
        dblist, err = process(cmd)
        print("returned: %s" % dblist)
        if err:
            assert_false(True, err)
        for db in dbs:
            default_db = re.compile("[\w\n]*%s[\w\n]*" % db)
            if not default_db.match(dblist):
                fail("No match for db %s in dblist. :(" % (db, dblist))

    def _check_connection(self, username, password):
        pos_error = re.compile("ERROR 1130 \(HY000\): Host '[\w\.]*' is not allowed to connect to this MySQL server")
        dblist, err = process("sudo mysql -h %s -u '%s' -p'%s' -e 'show databases;'"
                                % (instance_info.user_ip, username, password))
        if pos_error.match(err):
            assert_true(True)
        else:
            assert_false(True, err)

    def _verify_root_timestamp(self, id):
        mgmt_instance = dbaas.management.show(id)
        assert_true(mgmt_instance is not None)
        timestamp = mgmt_instance.root_enabled_at
        assert_equal(self.root_enabled_timestamp, timestamp)
        timestamp = dbaas.management.root_enabled_history(id).root_enabled_at
        print "REH is %s" % timestamp
        assert_equal(self.root_enabled_timestamp, timestamp)

    def _root(self):
        global dbaas
        global root_password
        host = "%"
        user, password = dbaas.root.create(instance_info.id)

        engine = init_engine(user, password, instance_info.user_ip)
        client = LocalSqlClient(engine)
        with client:
            t = text("""SELECT User, Host FROM mysql.user WHERE User=:user AND Host=:host;""")
            result = client.execute(t, user=user, host=host)
            for row in result:
                assert_equal(user, row['User'])
                assert_equal(host, row['Host'])
        root_password = password
        self.root_enabled_timestamp = dbaas.management.show(instance_info.id).root_enabled_at
        assert_not_equal(self.root_enabled_timestamp, 'Never')

    @test(depends_on=[test_delete_users])
    def test_root_initially_disabled(self):
        """Test that root is disabled"""
        enabled = dbaas.root.is_root_enabled(instance_info.id)
        assert_false(enabled, "Root SHOULD NOT be enabled.")

    @test(depends_on=[test_delete_users, test_root_initially_disabled])
    def test_root_initially_disabled_details(self):
        """Use instance details to test that root is disabled."""
        instance = dbaas.instances.get(instance_info.id)
        assert_true(hasattr(instance, 'rootEnabled'), "Instance has no rootEnabled property.")
        assert_false(instance.rootEnabled, "Root SHOULD NOT be enabled.")
        assert_equal(self.root_enabled_timestamp, 'Never')
        self._verify_root_timestamp(instance_info.id)

    @test(depends_on=[test_root_initially_disabled_details])
    def test_enable_root(self):
        self._root()
        assert_not_equal(self.root_enabled_timestamp, 'Never')

    @test(depends_on=[test_enable_root])
    def test_root_now_enabled(self):
        """Test that root is now enabled."""
        enabled = dbaas.root.is_root_enabled(instance_info.id)
        assert_true(enabled, "Root SHOULD be enabled.")

    @test(depends_on=[test_root_now_enabled])
    def test_root_now_enabled_details(self):
        """Use instance details to test that root is now enabled."""
        instance = dbaas.instances.get(instance_info.id)
        assert_true(hasattr(instance, 'rootEnabled'), "Instance has no rootEnabled property.")
        assert_true(instance.rootEnabled, "Root SHOULD be enabled.")
        assert_not_equal(self.root_enabled_timestamp, 'Never')
        self._verify_root_timestamp(instance_info.id)

    @test(depends_on=[test_root_now_enabled_details])
    def test_reset_root(self):
        old_ts = self.root_enabled_timestamp
        self._root()
        assert_not_equal(self.root_enabled_timestamp, 'Never')
        assert_equal(self.root_enabled_timestamp, old_ts)

    @test(depends_on=[test_reset_root])
    def test_root_still_enabled(self):
        """Test that after root was reset it's still enabled."""
        enabled = dbaas.root.is_root_enabled(instance_info.id)
        assert_true(enabled, "Root SHOULD still be enabled.")

    @test(depends_on=[test_root_still_enabled])
    def test_root_still_enabled_details(self):
        """Use instance details to test that after root was reset it's still enabled."""
        instance = dbaas.instances.get(instance_info.id)
        assert_true(hasattr(instance, 'rootEnabled'), "Instance has no rootEnabled property.")
        assert_true(instance.rootEnabled, "Root SHOULD still be enabled.")
        assert_not_equal(self.root_enabled_timestamp, 'Never')
        self._verify_root_timestamp(instance_info.id)

    @test(depends_on=[test_root_still_enabled_details])
    def test_reset_root_user_enabled(self):
        created_users= ['root']
        self.system_users.remove('root')
        users = dbaas.users.list(instance_info.id)
        found = False
        for user in created_users:
            found = any(result.name == user for result in users)
            assert_true(found, "User '%s' not found in result" %user)
            found = False

        found = False
        for user in self.system_users:
            found = any(result.name == user for result in users)
            assert_false(found, "User '%s' SHOULD NOT BE found in result" %user)
            found = False
        assert_not_equal(self.root_enabled_timestamp, 'Never')
        self._verify_root_timestamp(instance_info.id)