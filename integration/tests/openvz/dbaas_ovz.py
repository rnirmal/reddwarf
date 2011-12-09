import sys
import time
import re

from nova import context
from nova import db

from proboscis import before_class
from proboscis import test
from proboscis.asserts import assert_equal
from proboscis.asserts import assert_false
from proboscis.asserts import assert_not_equal
from proboscis.asserts import assert_raises
from proboscis.asserts import assert_true
from proboscis.asserts import fail
from proboscis.decorators import time_out
from tests.api.instances import instance_info
from tests.api.instances import GROUP_START
from tests.api.instances import GROUP_TEST
from tests.util import get_vz_ip_for_device
from tests.util import process
from tests.util import string_in_list


@test(depends_on_groups=[GROUP_START], groups=[GROUP_TEST, "dbaas.guest.ovz"])
class TestMultiNic(object):
    """
        Test that the created instance has 2 nics with the specified ip
        address as allocated to it.
    """

    @before_class
    def setUp(self):
        instance_info.user_ip = get_vz_ip_for_device(instance_info.local_id,
                                                      "eth0")

    @test
    def test_multi_nic(self):
        """
        Multinic - Verify that nics as specified in the database are created
        in the guest
        """
        vifs = db.virtual_interface_get_by_instance(context.get_admin_context(),
                                                    instance_info.local_id)
        for vif in vifs:
            fixed_ip = db.fixed_ip_get_by_virtual_interface(context.get_admin_context(),
                                                            vif['id'])
            vz_ip = get_vz_ip_for_device(instance_info.local_id,
                                         vif['network']['bridge_interface'])
            assert_equal(vz_ip, fixed_ip[0]['address'])


@test(depends_on_classes=[TestMultiNic], groups=[GROUP_TEST, "dbaas.guest.mysql"])
class TestMysqlAccess(object):
    """
        Test Access to the mysql server as os_admin and root
    """

    def _mysql_error_handler(self, err):
        pos_error = re.compile("ERROR 1130 \(HY000\): Host '[\w\.]*' is not allowed to connect to this MySQL server")
        pos_error1 = re.compile("ERROR 1045 \(28000\): Access denied for user '[\w]*'@'[\w\.]*' \(using password: (YES|NO)\)")
        neg_error = re.compile("ERROR 2003 \(HY000\): Can't connect to MySQL server on *")
        if pos_error.match(err) or pos_error1.match(err):
            pass
        elif neg_error.match(err):
            fail(err)
        else:
            raise RuntimeError(err)

    @time_out(60 * 2)
    @test
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

    @test
    def test_mysql_root(self):
        out, err = process("mysql -h %s -u root -pdsfgnear"
                           % instance_info.user_ip)
        self._mysql_error_handler(err)

    @test
    def test_zfirst_db(self):
        if not instance_info.check_database("firstdb"):
            fail("Database 'firstdb' was not created")
