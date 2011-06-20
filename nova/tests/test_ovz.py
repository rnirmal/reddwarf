# vim: tabstop=4 shiftwidth=4 softtabstop=4

import mox

from nova import exception
from nova import flags
from nova import test
from nova.compute import power_state
from nova.virt import openvz_conn

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

meminfo = """MemTotal:         506128 kB
MemFree:          291992 kB
Buffers:           44512 kB
Cached:            64708 kB
SwapCached:            0 kB
Active:           106496 kB
Inactive:          62948 kB
Active(anon):      62108 kB
Inactive(anon):      496 kB
Active(file):      44388 kB
Inactive(file):    62452 kB
Unevictable:        2648 kB
Mlocked:            2648 kB
SwapTotal:       1477624 kB
SwapFree:        1477624 kB
Dirty:                 0 kB
Writeback:             0 kB
AnonPages:         62908 kB
Mapped:            14832 kB
Shmem:               552 kB
Slab:              27988 kB
SReclaimable:      17280 kB
SUnreclaim:        10708 kB
KernelStack:        1448 kB
PageTables:         3092 kB
NFS_Unstable:          0 kB
Bounce:                0 kB
WritebackTmp:          0 kB
CommitLimit:     1730688 kB
Committed_AS:     654760 kB
VmallocTotal:   34359738367 kB
VmallocUsed:       24124 kB
VmallocChunk:   34359711220 kB
HardwareCorrupted:     0 kB
HugePages_Total:       0
HugePages_Free:        0
HugePages_Rsvd:        0
HugePages_Surp:        0
Hugepagesize:       2048 kB
DirectMap4k:        8128 kB
DirectMap2M:      516096 kB
"""

utility = {
    'CTIDS': {
        1: {

        }
    },
    'UTILITY': 10000,
    'TOTAL': 1000,
    'UNITS': 100000,
    'MEMORY_MB': 512000,
    'CPULIMIT': 2400
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
        conn = openvz_conn.OpenVzConnection(False)
        self.mox.StubOutWithMock(conn, '_percent_of_resource')
        conn._percent_of_resource(mox.IgnoreArg()).MultipleTimes().AndReturn(.5)
        self.mox.StubOutWithMock(conn, 'utility')
        conn.utility = utility
        self.mox.ReplayAll()
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
        conn = openvz_conn.OpenVzConnection(False)
        self.mox.StubOutWithMock(conn, '_percent_of_resource')
        conn._percent_of_resource(mox.IgnoreArg()).MultipleTimes().AndReturn(.5)
        self.mox.StubOutWithMock(conn, 'utility')
        conn.utility = utility
        self.mox.ReplayAll()
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
        conn = openvz_conn.OpenVzConnection(False)
        self.mox.StubOutWithMock(conn, '_percent_of_resource')
        conn._percent_of_resource(mox.IgnoreArg()).AndReturn(.5)
        self.mox.StubOutWithMock(conn, 'utility')
        conn.utility = utility
        self.mox.ReplayAll()
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
        conn = openvz_conn.OpenVzConnection(False)
        self.mox.StubOutWithMock(conn, '_percent_of_resource')
        conn._percent_of_resource(mox.IgnoreArg()).AndReturn(.5)
        self.mox.StubOutWithMock(conn, 'utility')
        conn.utility = utility
        self.mox.ReplayAll()
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

    def test_calc_pages_success(self):
        # this test is a little sketchy because it is testing the default
        # values of memory for instance type id 1.  if this value changes then
        # we will have a mismatch.

        # TODO(imsplitbit): make this work better.
        conn = openvz_conn.OpenVzConnection(False)
        self.assertEqual(conn._calc_pages(test_instance), 1048576)

    def test_get_cpuunits_capability_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute(mox.IgnoreArg(),
                                  mox.IgnoreArg()).AndReturn(('',''))
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        self.assertTrue(conn._get_cpuunits_capability())

    def test_percent_of_resource(self):
        conn = openvz_conn.OpenVzConnection(False)
        self.mox.StubOutWithMock(conn, 'utility')
        conn.utility = utility
        self.mox.ReplayAll()
        self.assertEqual(float, type(conn._percent_of_resource(test_instance)))

    def test_get_memory_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute(mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg()).AndReturn((meminfo, ''))
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        conn._get_memory()
        self.assertEquals(int, type(conn.utility['MEMORY_MB']))
        self.assertGreater(conn.utility['MEMORY_MB'], 0)

    def test_get_memory_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute(mox.IgnoreArg(),
                                  mox.IgnoreArg(),
                                  mox.IgnoreArg()).AndRaise(
            exception.ProcessExecutionError)
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        self.assertRaises(exception.Error, conn._get_memory)

        
