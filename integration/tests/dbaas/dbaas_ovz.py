import gettext
import os
import subprocess
import sys
import time
import pexpect
import re
import unittest
from pexpect import TIMEOUT

possible_topdir = os.path.normpath(os.path.join(os.path.abspath(sys.argv[0]),
                                   os.pardir,
                                   os.pardir))
if os.path.exists(os.path.join(possible_topdir, 'nova', '__init__.py')):
    sys.path.insert(0, possible_topdir)

gettext.install('nova', unicode=1)


from datetime import datetime
from nose.plugins.skip import SkipTest
from nova import utils
from novaclient.exceptions import NotFound
from sqlalchemy import create_engine
from sqlalchemy.sql.expression import text

from dbaas import Dbaas
from nova.guest.dbaas import LocalSqlClient
from tests.util import test_config
from proboscis.decorators import expect_exception
from proboscis.decorators import time_out
from proboscis import test
from tests.util.users import Requirements
from tests.util import string_in_list


dbaas = None
dbaas_flavor = None
dbaas_flavor_href = None
dbaas_image = None
dbaas_image_href = None
container_name = None
success_statuses = ["build", "active"]
container_result = None
container_id = None
container_ip = None
pid = None


def _process(cmd):
    process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
    result = process.communicate()
    return result


def _check_database(dbname):
    global container_id
    default_db = re.compile("[\w\n]*%s[\w\n]*" % dbname)
    dblist, err = _process("sudo vzctl exec %s \"mysql -e 'show databases';\""
                            % container_id)
    if err:
        raise RuntimeError(err)
    if default_db.match(dblist):
        return True
    else:
        return False


def _init_engine(user, password, host):
    return create_engine("mysql://%s:%s@%s:3306" %
                               (user, password, host),
                               pool_recycle=1800, echo=True)


class Base(unittest.TestCase):

    def assume(self, condition, msg=None):
        if not condition:
            raise SkipTest(msg)

    def assume_container_created(self):
        global container_result
        self.assume(container_result != None, "container_result not defined.")


@test(groups=["dbaas.guest"], depends_on_groups=["services.initialize"])
class Setup(Base):
    """Makes sure the client can hit the ReST service.

    This test also uses the API to find the image and flavor to use.

    """

    def setUp(self):
        global dbaas
        global user
        user = test_config.users.find_user(Requirements(is_admin=True))
        test_config.nova.ensure_started()
        dbaas = Dbaas(user.auth_user, user.auth_key, test_config.dbaas.url)
        dbaas.authenticate()


    def test_find_image(self):
        global dbaas
        global user
        self.assertNotEqual(None, test_config.dbaas_image)
        images = dbaas.images.list()
        global dbaas_image
        global dbaas_image_href
        for image in images:
            if int(image.id) == test_config.dbaas_image:
                dbaas_image = image
                for link in dbaas_image.links:
                    if link['rel'] == "self":
                        dbaas_image_href = link['href']
                if not dbaas_image_href:
                    raise Exception("Found image with ID %s, but it had no " 
                                    "self href!" % str(test_config.dbaas_image))
        self.assertNotEqual(None, dbaas_image)

    def test_find_flavor(self):
        global dbaas
        global user
        self.assertNotEqual(None, test_config.dbaas_image)
        flavors = dbaas.flavors.list()
        global dbaas_flavor
        global dbaas_flavor_href
        for flavor in flavors:
            if int(flavor.id) == 1:
                dbaas_flavor = flavor
                for link in dbaas_flavor.links:
                    if link['rel'] == "self":
                        dbaas_flavor_href = link['href']
                if not dbaas_flavor_href:
                    raise Exception("Found flavor with ID %s, but it had no "
                                    "self href!" % str(1))
        self.assertNotEqual(None, dbaas_flavor)

    def test_create_container_name(self):
        global container_name
        container_name = "TEST_" + str(datetime.now())

@test(depends_on_classes=[Setup], groups=["dbaas.guest"])
class CreateContainer(Base):
    """Test to create a Database Container

    If the call returns without raising an exception this test passes.

    """

    def test_create(self):

        global dbaas_image
        if dbaas_image is None:
            raise SkipTest("Setup failed")

        global dbaas
        global dbaas_image_href
        global container_result
        global container_id
        # give the services some time to start up
        time.sleep(2)

        databases = []
        databases.append({"name": "firstdb", "charset": "latin2",
                          "collate": "latin2_general_ci"})

        container_result = dbaas.dbcontainers.create(container_name,
                                                     dbaas_flavor_href,
                                                     dbaas_image_href,
                                                     databases)
        container_id = container_result.id


@test(depends_on_classes=[CreateContainer], groups=["dbaas.guest"])
class VerifyGuestStarted(Base):
    """
        Test to verify the guest container is started and we can get the init
        process pid.
    """

    @time_out(60 * 8)
    def test_container_created(self):
        while True:
            status, err = _process("sudo vzctl status %s | awk '{print $5}'"
                                  % str(container_id))

            if not string_in_list(status, ["running"]):
                time.sleep(5)
            else:
                self.assertEquals("running", status.strip())
                break


    @time_out(60 * 10)
    def test_get_init_pid(self):
        global pid
        while True:
            out, err = _process("pstree -ap | grep init | cut -d',' -f2 | vzpid - | grep %s | awk '{print $1}'"
                                % str(container_id))
            pid = out.strip()
            if not pid:
                time.sleep(10)
            else:
                break


@test(depends_on_classes=[VerifyGuestStarted], groups=["dbaas.guest"])
class WaitForGuestInstallationToFinish(Base):
    """
        Wait until the Guest is finished installing.  It takes quite a while...
    """

    @time_out(60 * 8)
    def test_container_created(self):
        #/vz/private/1/var/log/nova/nova-guest.log
        while True:
            status, err = _process(
                """cat /vz/private/%s/var/log/nova/nova-guest.log | grep "Dbaas" """
                % str(container_id))
            if not string_in_list(status, ["Dbaas preparation complete."]):
                time.sleep(5)
            else:
                break


@test(depends_on_classes=[WaitForGuestInstallationToFinish], groups=["dbaas.guest"])
class TestGuestProcess(Base):
    """
        Test that the guest process is started with all the right parameters
    """

    @time_out(60 * 10)
    def test_guest_process(self):
        init_proc = re.compile("[\w\W\|\-\s\d,]*nova-guest --flagfile=/etc/nova/nova.conf nova[\W\w\s]*")
        guest_proc = re.compile("[\w\W\|\-\s]*/usr/bin/nova-guest --flagfile=/etc/nova/nova.conf[\W\w\s]*")
        apt = re.compile("[\w\W\|\-\s]*apt-get[\w\W\|\-\s]*")
        while True:
            guest_process, err = _process("pstree -ap %s | grep nova-guest"
                                            % pid)
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


@test(depends_on_classes=[TestGuestProcess], groups=["dbaas.guest",
                                                     "dbaas.guest.mysql"])
class TestMysqlAccess(Base):
    """
        Test Access to the mysql server as os_admin and root
    """

    def setUp(self):
        global container_id
        global container_ip
        if not container_id:
            raise SkipTest("container_id is None!")
        ip, err = _process("""sudo vzctl exec %s ifconfig eth0 | grep 'inet addr' """
                           """| awk '{gsub(/addr:/, "");print $2}' """
                            % container_id)
        if err:
            self.assertFalse(True, err)
        container_ip = ip.strip()

    def _mysql_error_handler(self, err):
        global container_ip
        pos_error = re.compile("ERROR 1130 \(HY000\): Host '[\w\.]*' is not allowed to connect to this MySQL server")
        pos_error1 = re.compile("ERROR 1045 \(28000\): Access denied for user '[\w]*'@'[\w\.]*' \(using password: (YES|NO)\)")
        neg_error = re.compile("ERROR 2003 \(HY000\): Can't connect to MySQL server on *")
        if pos_error.match(err) or pos_error1.match(err):
            self.assertTrue(True, err)
        elif neg_error.match(err):
            self.assertFalse(True, err)
        else:
            raise RuntimeError(err)

    def test_mysql_admin(self):
        global container_ip
        while True:
            mysqld, err = _process("pstree -a %s | grep mysqld" % pid)
            if not string_in_list(mysqld, ["mysqld"]):
                time.sleep(10)
            else:
                time.sleep(10)
                out, err = _process("mysql -h %s -u os_admin -pasdfd-asdf234"
                                    % container_ip)
                self._mysql_error_handler(err)
                break

    def test_mysql_root(self):
        global container_id
        out, err = _process("mysql -h %s -u root -pdsfgnear" % container_ip)
        self._mysql_error_handler(err)

    def test_zfirst_db(self):
        if _check_database("firstdb"):
            self.assertTrue(True)
        else:
            self.assertFalse(True)


@test(depends_on_classes=[TestMysqlAccess], groups=["dbaas.guest",
                                                    "dbaas.guest.mysql"])
class TestDatabases(Base):
    """
    Test the creation and deletion of additional MySQL databases
    """

    dbname = "third #?@some_-"
    dbname_regex = "third\s\#\?\@some\_\-"
    dbname_urlencoded = "third%20%23%3F%40some_-"

    def test_create_database(self):
        databases = list()
        databases.append({"name": self.dbname, "charset": "latin2",
                          "collate": "latin2_general_ci"})

        global dbaas
        global container_id
        dbaas.databases.create(container_id, databases)
        time.sleep(5)

        if _check_database(self.dbname_regex):
            self.assertTrue(True)
        else:
            self.assertFalse(True)

    @expect_exception(NotFound)
    def test_create_database_on_missing_container(self):
        databases = [{"name": "invalid_db", "charset": "latin2",
                      "collate": "latin2_general_ci"}]
        global dbaas
        global container_id
        dbaas.databases.create(-1, databases)

    @expect_exception(NotFound)
    def test_delete_database_on_missing_container(self):
        global dbaas
        dbaas.databases.delete(-1,  self.dbname_urlencoded)

    def test_delete_database(self):
        global dbaas
        global container_id
        dbaas.databases.delete(container_id, self.dbname_urlencoded)
        time.sleep(5)

        if not _check_database(self.dbname):
            self.assertTrue(True)
        else:
            self.assertFalse(True)


@test(depends_on_classes=[TestDatabases], groups=["dbaas.guest",
                                                  "dbaas.guest.mysql"])
class TestUsers(Base):
    """
    Test the creation and deletion of users
    """

    username = "testuser"
    password = "testpassword"
    username1 = "anouser"
    password1 = "anopassword"
    db1 = "TESTDB"
    db2 = "firstdb"

    def test_create_users(self):
        users = []
        users.append({"name": self.username, "password": self.password,
                      "database": self.db1})
        users.append({"name": self.username1, "password": self.password1,
                     "databases": [{"name": self.db1}, {"name": self.db2}]})

        global dbaas
        global container_id
        dbaas.users.create(container_id, users)
        time.sleep(5)

        self._check_database_for_user(self.username, self.password,
                                    [self.db1])
        self._check_database_for_user(self.username1, self.password1,
                                    [self.db1, self.db2])

    def test_delete_users(self):
        global dbaas
        dbaas.users.delete(container_id, self.username)
        dbaas.users.delete(container_id, self.username1)
        time.sleep(5)

        self._check_connection(self.username, self.password)
        self._check_connection(self.username1, self.password1)

    def _check_database_for_user(self, user, password, dbs):
        global container_ip
        dblist, err = _process("sudo mysql -h %s -u %s -p%s -e 'show databases;'"
                                % (container_ip, user, password))
        if err:
            self.assertFalse(True, err)
        for db in dbs:
            default_db = re.compile("[\w\n]*%s[\w\n]*" % db)
            if not default_db.match(dblist):
                self.assertFalse(True, dblist)
        self.assertTrue(True)

    def _check_connection(self, username, password):
        global container_ip
        pos_error = re.compile("ERROR 1130 \(HY000\): Host '[\w\.]*' is not allowed to connect to this MySQL server")
        dblist, err = _process("sudo mysql -h %s -u %s -p%s -e 'show databases;'"
                                % (container_ip, username, password))
        if pos_error.match(err):
            self.assertTrue(True)
        else:
            self.assertFalse(True, err)

    def _root(self):
        global dbaas
        global container_id
        global container_ip
        global root_password
        host = "%"
        user, password = dbaas.root.create(container_id)

        engine = _init_engine(user, password, container_ip)
        client = LocalSqlClient(engine)
        with client:
            t = text("""SELECT User, Host FROM mysql.user WHERE User=:user AND Host=:host;""")
            result = client.execute(t, user=user, host=host)
            for row in result:
                self.assertEquals(user, row['User'])
                self.assertEquals(host, row['Host'])
        root_password = password

    def test_enable_root(self):
        self._root()

    def test_reset_root(self):
        self._root()

    def test_zdisable_root(self):
        global dbaas
        global container_id
        global container_ip
        global root_password
        user = "root"
        host = "%"
        dbaas.root.delete(container_id)

        try:
            engine = _init_engine(user, root_password, container_ip)
            client = LocalSqlClient(engine)
            with client:
                t = text("""SELECT * FROM mysql.user where User=:user, Host=:host;""")
                client.execute(t, user=user, host=host)
            self.fail("Should have raised exception.")
        except:
            pass



@test(depends_on_classes=[TestUsers], groups=["dbaas.guest"])
class DeleteContainer(Base):
    """ Delete the created container """

    @time_out(6 * 60)
    def test_delete(self):
        global container_result
        global dbaas

        dbaas.dbcontainers.delete(container_result)
        try:
            while container_result:
                container_result = dbaas.dbcontainers.get(container_result)
        except NotFound:
            pass
