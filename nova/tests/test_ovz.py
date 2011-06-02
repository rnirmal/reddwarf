# vim: tabstop=4 shiftwidth=4 softtabstop=4

#import eventlet
import mox
#import os
#import re
#import sys

#from nova import context
#from nova import db
from nova import exception
from nova import flags
from nova import test
#from nova import utils
#from nova.api.ec2 import cloud
#from nova.auth import manager
#from nova.compute import manager as compute_manager
from nova.compute import power_state
#from nova.db.sqlalchemy import models
from nova.virt import openvz_conn
#from nose.tools import raises

FLAGS = flags.FLAGS

test_instance = {
    "image_id": 1,
    "name": "instance-0000001",
    "instance_type_id": 1,
    "id": 1002
}

vz_list = "\t1001\n\t1002\n\t1003\n\t1004\n"

vz_name = """\tinstance-00001001\n"""

vz_names = """\tinstance-00001001\n\tinstance-00001002
              \tinstance-00001003\n\tinstance-00001004\n"""

good_status = {
    'state': power_state.RUNNING,
    'max_mem': 0,
    'mem': 0,
    'num_cpu': 0,
    'cpu_time': 0
}

class OpenVzConnTestCase(test.TestCase):
    def setUp(self):
        super(OpenVzConnTestCase, self).setUp()

    def test_list_instances_detail_success(self):
         # Testing happy path of OpenVzConnection.list_instances()
         self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
         openvz_conn.utils.execute(mox.IgnoreArg(),
                                   mox.IgnoreArg(),
                                   mox.IgnoreArg(),
                                   mox.IgnoreArg(),
                                   mox.IgnoreArg(),
                                   mox.IgnoreArg()).AndReturn((vz_names, None))
         conn = openvz_conn.OpenVzConnection(False)
         self.mox.StubOutWithMock(conn, 'get_info')
         conn.get_info(mox.IgnoreArg()).MultipleTimes().AndReturn(good_status)

         # Start test
         self.mox.ReplayAll()

         vzs = conn.list_instances_detail()
         self.assertEqual(vzs.__class__, list)

    def test_list_instances_detail_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute(mox.IgnoreArg(),
                                   mox.IgnoreArg(),
                                   mox.IgnoreArg(),
                                   mox.IgnoreArg(),
                                   mox.IgnoreArg(),
                                   mox.IgnoreArg()).AndRaise(exception.ProcessExecutionError)
        conn = openvz_conn.OpenVzConnection(False)

        self.mox.ReplayAll()

        self.assertRaises(exception.Error, conn.list_instances_detail)

    def test_start_success(self):
        # Testing happy path :-D
        # Mock the objects needed for this test to succeed.
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute(mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg()).AndReturn(('', None))
        self.mox.StubOutWithMock(openvz_conn.db, 'instance_set_state')
        openvz_conn.db.instance_set_state(mox.IgnoreArg(),
                                          mox.IgnoreArg(),
                                          mox.IgnoreArg())

        # Start the tests
        self.mox.ReplayAll()

        # Create our connection object.  For all intents and purposes this is
        # a real OpenVzConnection object.
        conn = openvz_conn.OpenVzConnection(True)
        self.assertTrue(conn._start(test_instance))

    def test_start_fail(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute(mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg()).AndRaise(exception.ProcessExecutionError)
        self.mox.ReplayAll()

        conn = openvz_conn.OpenVzConnection(False)
        self.assertRaises(exception.Error, conn._start, test_instance)


    def test_list_instances_success(self):
        # Testing happy path of OpenVzConnection.list_instances()
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute(mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg()).AndReturn((vz_list, None))

        # Start test
        self.mox.ReplayAll()

        conn = openvz_conn.OpenVzConnection(False)
        vzs = conn.list_instances()
        self.assertEqual(vzs.__class__, list)

    def test_list_instances_fail(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute(mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg()).AndRaise(exception.Error)

        # Start test
        self.mox.ReplayAll()

        conn = openvz_conn.OpenVzConnection(False)
        self.assertRaises(exception.Error, conn.list_instances)

    def test_create_vz_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute(mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg()).AndReturn(('', ''))
        self.mox.ReplayAll()

        conn = openvz_conn.OpenVzConnection(False)
        self.assertTrue(conn._create_vz(test_instance))

    def test_create_vz_fail(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute(mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg()).AndRaise(
            exception.ProcessExecutionError)
        self.mox.ReplayAll()

        conn = openvz_conn.OpenVzConnection(False)
        self.assertRaises(exception.Error, conn._create_vz, test_instance)

    def test_set_vz_os_hint_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute(mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg()).AndReturn(('',''))
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        self.assertTrue(conn._set_vz_os_hint(test_instance))

    def test_set_vz_os_hint_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute(mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg()).AndRaise(
            exception.ProcessExecutionError)
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        self.assertRaises(exception.Error, conn._set_vz_os_hint, test_instance)

    def test_configure_vz_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute(mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg()).AndReturn(('',''))
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        self.assertTrue(conn._configure_vz(test_instance))

    def test_configure_vz_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute(mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg()).AndRaise(
            exception.ProcessExecutionError)
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        self.assertRaises(exception.Error, conn._configure_vz, test_instance)

    def test_stop_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute(mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg()).AndReturn(('',''))
        self.mox.StubOutWithMock(openvz_conn.db, 'instance_set_state')
        openvz_conn.db.instance_set_state(mox.IgnoreArg(),
                                          mox.IgnoreArg(),
                                          mox.IgnoreArg())
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        self.assertTrue(conn._stop(test_instance))

    def test_stop_failure_on_exec(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute(mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg()).AndRaise(
            exception.ProcessExecutionError)
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        self.assertRaises(exception.Error, conn._stop, test_instance)

    def test_stop_failure_on_db_access(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute(mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg()).AndReturn(('',''))
        self.mox.StubOutWithMock(openvz_conn.db, 'instance_set_state')
        openvz_conn.db.instance_set_state(mox.IgnoreArg(),
                                          mox.IgnoreArg(),
                                          mox.IgnoreArg()).AndRaise(
            exception.DBError('FAIL'))
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        self.assertRaises(exception.Error, conn._stop, test_instance)

    def test_add_netif_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute(mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg()).AndReturn(('',''))
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        self.assertTrue(conn._add_netif(test_instance))

    def test_add_netif_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute(mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg()).AndRaise(
            exception.ProcessExecutionError)
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        self.assertRaises(exception.Error, conn._add_netif, test_instance)

    def test_set_vmguarpages_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute(mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg()).AndReturn(('',''))
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        self.assertTrue(conn._set_vmguarpages(test_instance))

    def test_set_vmguarpages_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute(mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg()).AndRaise(
            exception.ProcessExecutionError)
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        self.assertRaises(exception.Error, conn._set_vmguarpages, test_instance)

    def test_set_privvmpages_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute(mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg()).AndReturn(('',''))
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        self.assertTrue(conn._set_privvmpages(test_instance))

    def test_set_privvmpages_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute(mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg()).AndRaise(
            exception.ProcessExecutionError)
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        self.assertRaises(exception.Error, conn._set_privvmpages, test_instance)

    def test_set_cpuunits_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute(mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg()).AndReturn(('',''))
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        self.assertTrue(conn._set_cpuunits(test_instance))

    def test_set_cpuunits_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute(mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg()).AndRaise(
            exception.ProcessExecutionError)
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        self.assertRaises(exception.Error, conn._set_cpuunits, test_instance)

    def test_set_cpulimit_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute(mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg()).AndReturn(('',''))
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        self.assertTrue(conn._set_cpulimit(test_instance))

    def test_set_cpulimit_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute(mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg()).AndRaise(
            exception.ProcessExecutionError)
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        self.assertRaises(exception.Error, conn._set_cpulimit, test_instance)

    def test_set_cpus_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute(mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg()).AndReturn(('',''))
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        self.assertTrue(conn._set_cpus(test_instance))

    def test_set_cpus_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute(mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg()).AndRaise(
            exception.ProcessExecutionError)
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        self.assertRaises(exception.Error, conn._set_cpus, test_instance)

#    def test_set_nameserver_success(self):
#        self.mox.StubOutWithMock(openvz_conn.context, 'get_admin_context')
#        openvz_conn.context.get_admin_context().AndReturn(True)
#
#        self.mox.StubOutWithMock(openvz_conn.db, 'instance_get_fixed_address')
#        openvz_conn.db.instance_get_fixed_address(mox.IgnoreArg(),
#                                                  mox.IgnoreArg()).AndReturn(
#            '1.1.1.1'
#        )
