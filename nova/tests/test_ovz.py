# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2010 OpenStack LLC.
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

import mox
import __builtin__
from nova import exception
from nova import flags
from nova import test
from nova.compute import power_state
from nova.virt import openvz_conn
from StringIO import StringIO

FLAGS = flags.FLAGS

INSTANCE = {
    "image_ref": 1,
    "name": "instance-00001002",
    "instance_type_id": 1,
    "id": 1002,
    "volumes": [
        {
            "uuid": "776E384C-47FF-433D-953B-61272EFDABE1",
            "mountpoint": "/var/lib/mysql"
        },
        {
            "uuid": False,
            "dev": "/dev/sda1",
            "mountpoint": "/var/tmp"
        }
    ]
}

RES_PERCENT = .50

VZLIST = "\t1001\n\t%d\n\t1003\n\t1004\n" % (INSTANCE['id'],)

VZNAME = """\tinstance-00001001\n"""

VZNAMES = """\tinstance-00001001\n\t%s
              \tinstance-00001003\n\tinstance-00001004\n""" % (
    INSTANCE['name'],)

GOODSTATUS = {
    'state': power_state.RUNNING,
    'max_mem': 0,
    'mem': 0,
    'num_cpu': 0,
    'cpu_time': 0
}

ERRORMSG = "vz command ran but output something to stderr"

MEMINFO = """MemTotal:         506128 kB
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

UTILITY = {
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

CPUCHECKCONT = """VEID		CPUUNITS
-------------------------
0		1000
26		25000
27		25000
Current CPU utilization: 51000
Power of the node: 758432
"""

CPUCHECKNOCONT = """Current CPU utilization: 51000
Power of the node: 758432
"""

FILECONTENTS = """mount UUID=FEE52433-F693-448E-B6F6-AA6D0124118B /mnt/foo
        mount --bind /mnt/foo /vz/private/1/mnt/foo
        """

NETWORKINFO = [
	[
		{
			u'bridge': u'br100',
			u'multi_host': False,
			u'bridge_interface': u'eth0',
			u'vlan': None,
			u'id': 1,
			u'injected': True,
			u'cidr': u'10.0.2.0/24',
			u'cidr_v6': None
		},
		{
			u'should_create_bridge': True,
			u'dns': [
					u'192.168.2.1'
				],
			u'label': u'usernet',
			u'broadcast': u'10.0.2.255',
			u'ips': [
					{
						u'ip': u'10.0.2.16',
						u'netmask': u'255.255.255.0',
						u'enabled':
						u'1'
					}
				],
			u'mac': u'02:16:3e:0c:2c:08',
			u'rxtx_cap': 0,
			u'should_create_vlan': True,
			u'dhcp_server': u'10.0.2.2',
			u'gateway': u'10.0.2.2'
		}
	],
	[
		{
			u'bridge': u'br200',
			u'multi_host': False,
			u'bridge_interface': u'eth1',
			u'vlan': None,
			u'id': 2,
			u'injected': True,
			u'cidr': u'10.0.4.0/24',
			u'cidr_v6': None
		},
		{
			u'should_create_bridge': False,
			u'dns': [
					u'192.168.2.1'
				],
			u'label': u'infranet',
			u'broadcast': u'10.0.4.255',
			u'ips': [
					{
						u'ip': u'10.0.4.16',
						u'netmask':
						u'255.255.255.0',
						u'enabled': u'1'
					}
				],
			u'mac': u'02:16:3e:40:5e:1b',
			u'rxtx_cap': 0,
			u'should_create_vlan': False,
			u'dhcp_server':	u'10.0.2.2',
			u'gateway': u'10.0.2.2'
		}
	]
]

INTERFACEINFO = [
    {
        'id': 1,
        'interface_number': 0,
        'bridge': 'br100',
        'name': 'eth0',
        'mac': '02:16:3e:0c:2c:08',
        'address': '10.0.2.16',
        'netmask': '255.255.255.0',
        'gateway': '10.0.2.2',
        'broadcast': '10.0.2.255',
        'dns': '192.168.2.1',
        'address_v6': None,
        'gateway_v6': None,
        'netmask_v6': None
    },
    {
        'id': 1,
        'interface_number': 1,
        'bridge': 'br200',
        'name': 'eth1',
        'mac': '02:16:3e:40:5e:1b',
        'address': '10.0.4.16',
        'netmask': '255.255.255.0',
        'gateway': '10.0.2.2',
        'broadcast': '10.0.4.255',
        'dns': '192.168.2.1',
        'address_v6': None,
        'gateway_v6': None,
        'netmask_v6': None
    }
]

TEMPFILE = '/tmp/foo/file'

NETTEMPLATE = """
    # This file describes the network interfaces available on your system
    # and how to activate them. For more information, see interfaces(5).

    # The loopback network interface
    auto lo
    iface lo inet loopback

    #for $ifc in $interfaces
    auto ${ifc.name}
    iface ${ifc.name} inet static
            address ${ifc.address}
            netmask ${ifc.netmask}
            broadcast ${ifc.broadcast}
            gateway ${ifc.gateway}
            dns-nameservers ${ifc.dns}

    #if $use_ipv6
    iface ${ifc.name} inet6 static
        address ${ifc.address_v6}
        netmask ${ifc.netmask_v6}
        gateway ${ifc.gateway_v6}
    #end if

    #end for
    """

MEMORY = 536870912

MEMORYMB = 512

MEM_PAGES = 131072

VCPUS = 2

class OpenVzConnTestCase(test.TestCase):
    def setUp(self):
        super(OpenVzConnTestCase, self).setUp()
        try:
            FLAGS.injected_network_template
        except AttributeError as err:
            flags.DEFINE_string('injected_network_template',
                                'nova/virt/interfaces.template',
                                'Stub for network template for testing purposes'
            )
        self.fake_file = mox.MockAnything()
        self.fake_file.readlines().AndReturn(FILECONTENTS.split())
        self.fake_file.writelines(mox.IgnoreArg())
        self.fake_file.read().AndReturn(FILECONTENTS)

    def test_list_instances_detail_success(self):
        # Testing happy path of OpenVzConnection.list_instances()
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzlist', '--all', '-o', 'name', '-H',
                                  run_as_root=True).AndReturn((VZNAMES, None))
        conn = openvz_conn.OpenVzConnection(False)
        self.mox.StubOutWithMock(conn, 'get_info')
        conn.get_info(mox.IgnoreArg()).MultipleTimes().AndReturn(GOODSTATUS)

        # Start test
        self.mox.ReplayAll()

        vzs = conn.list_instances_detail()
        self.assertEqual(vzs.__class__, list)

    def test_list_instances_detail_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzlist', '--all', '-o', 'name', '-H',
                                   run_as_root=True) \
                                  .AndRaise(exception.ProcessExecutionError)
        conn = openvz_conn.OpenVzConnection(False)

        self.mox.ReplayAll()

        self.assertRaises(exception.Error, conn.list_instances_detail)

    def test_start_success(self):
        # Testing happy path :-D
        # Mock the objects needed for this test to succeed.
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'start', INSTANCE['id'],
                                  run_as_root=True).AndReturn(('', None))
        self.mox.StubOutWithMock(openvz_conn.db, 'instance_update')
        openvz_conn.db.instance_update(mox.IgnoreArg(),
                                       INSTANCE['id'],
                                       {'power_state': power_state.RUNNING})

        # Start the tests
        self.mox.ReplayAll()

        # Create our connection object.  For all intents and purposes this is
        # a real OpenVzConnection object.
        conn = openvz_conn.OpenVzConnection(True)
        conn._start(INSTANCE)

    def test_start_fail(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'start', INSTANCE['id'],
                                  run_as_root=True) \
                                 .AndRaise(exception.ProcessExecutionError)
        self.mox.ReplayAll()

        conn = openvz_conn.OpenVzConnection(False)
        self.assertRaises(exception.Error, conn._start, INSTANCE)

    def test_set_onboot_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', instance['id'],
                                  '--onboot', 'no', '--save',
                                  run_as_root=True)\
                                  .AndReturn(('', ''))
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        conn._set_onboot(INSTANCE)

    def test_set_onboot_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', instance['id'],
                                  '--onboot', 'no', '--save',
                                  run_as_root=True)\
                                  .AndRaise(exception.ProcessExecutionError)
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        conn._set_onboot(INSTANCE)

    def test_list_instances_success(self):
        # Testing happy path of OpenVzConnection.list_instances()
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzlist', '--all', '--no-header', '--output',
                                  'ctid', run_as_root=True)\
                                  .AndReturn((VZLIST, None))

        # Start test
        self.mox.ReplayAll()

        conn = openvz_conn.OpenVzConnection(False)
        vzs = conn.list_instances()
        self.assertEqual(vzs.__class__, list)

    def test_list_instances_fail(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzlist', '--all', '--no-header', '--output',
                                  'ctid', run_as_root=True)\
                                  .AndRaise(exception.Error)

        # Start test
        self.mox.ReplayAll()

        conn = openvz_conn.OpenVzConnection(False)
        self.assertRaises(exception.Error, conn.list_instances)

    def test_create_vz_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'create', INSTANCE['id'],
                                  '--ostemplate', INSTANCE['image_ref'],
                                  run_as_root=True).AndReturn(('', ''))
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        conn._create_vz(INSTANCE)

    def test_create_vz_fail(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'create', INSTANCE['id'],
                                  '--ostemplate', INSTANCE['image_ref'],
                                  run_as_root=True)\
                                  .AndRaise(exception.ProcessExecutionError)
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        self.assertRaises(exception.Error, conn._create_vz, INSTANCE)

    def test_set_vz_os_hint_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', INSTANCE['id'], '--save',
                                  '--ostemplate', 'ubuntu', run_as_root=True)\
                                  .AndReturn(('', ''))
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        conn._set_vz_os_hint(INSTANCE)

    def test_set_vz_os_hint_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', INSTANCE['id'],
                                  '--save', '--ostemplate', 'ubuntu',
                                  run_as_root=True)\
                                  .AndRaise(exception.ProcessExecutionError)
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        self.assertRaises(exception.Error, conn._set_vz_os_hint, INSTANCE)

    def test_configure_vz_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', INSTANCE['id'], '--save',
                                  '--applyconfig', 'basic', run_as_root=True)\
                                  .AndReturn(('', ''))
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        conn._configure_vz(INSTANCE)

    def test_configure_vz_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', INSTANCE['id'], '--save',
                                  '--applyconfig', 'basic', run_as_root=True)\
                                  .AndRaise(exception.ProcessExecutionError)
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        self.assertRaises(exception.Error, conn._configure_vz, INSTANCE)

    def test_stop_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'stop', INSTANCE['id'],
                                  run_as_root=True).AndReturn(('', ''))
        self.mox.StubOutWithMock(openvz_conn.db, 'instance_update')
        openvz_conn.db.instance_update(mox.IgnoreArg(),
                                       INSTANCE['id'],
                                       {'power_state': power_state.SHUTDOWN})
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        conn._stop(INSTANCE)

    def test_stop_failure_on_exec(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'stop', INSTANCE['id'],
                                  run_as_root=True)\
                                  .AndRaise(exception.ProcessExecutionError)
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        self.assertRaises(exception.Error, conn._stop, INSTANCE)

    def test_stop_failure_on_db_access(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'stop', INSTANCE['id'],
                                  run_as_root=True).AndReturn(('', ''))
        self.mox.StubOutWithMock(openvz_conn.db, 'instance_update')
        openvz_conn.db.instance_update(mox.IgnoreArg(),
                                       INSTANCE['id'],
                                       {'power_state': power_state.SHUTDOWN})\
                                       .AndRaise(exception.DBError('FAIL'))
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        self.assertRaises(exception.Error, conn._stop, INSTANCE)

    def test_set_vmguarpages_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', INSTANCE['id'], '--save',
                                  '--vmguarpages', MEM_PAGES,
                                  run_as_root=True).AndReturn(('', ''))
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        conn._set_vmguarpages(INSTANCE, MEM_PAGES)

    def test_set_vmguarpages_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', INSTANCE['id'], '--save',
                                  '--vmguarpages', MEM_PAGES,
                                  run_as_root=True)\
                                  .AndRaise(exception.ProcessExecutionError)
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        self.assertRaises(exception.Error, conn._set_vmguarpages,
                          INSTANCE, MEM_PAGES)

    def test_set_privvmpages_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', INSTANCE['id'], '--save',
                                  '--privvmpages', MEM_PAGES,
                                  run_as_root=True).AndReturn(('', ''))
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        conn._set_privvmpages(INSTANCE, MEM_PAGES)

    def test_set_privvmpages_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', INSTANCE['id'], '--save',
                                  '--privvmpages', MEM_PAGES,
                                  run_as_root=True)\
                                  .AndRaise(exception.ProcessExecutionError)
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        self.assertRaises(exception.Error, conn._set_privvmpages,
                          INSTANCE, MEM_PAGES)

    def test_set_kmemsize_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', INSTANCE['id'], '--save',
                                  '--kmemsize', mox.IgnoreArg(),
                                  run_as_root=True).AndReturn(('',''))
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        conn._set_kmemsize(INSTANCE, MEMORY)

    def test_set_kmemsize_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', INSTANCE['id'], '--save',
                                  '--kmemsize', mox.IgnoreArg(),
                                  run_as_root=True)\
                                  .AndRaise(exception.ProcessExecutionError)
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        self.assertRaises(exception.Error, conn._set_kmemsize,
                          INSTANCE, MEMORY)

    def test_set_cpuunits_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', INSTANCE['id'], '--save',
                                  '--cpuunits', UTILITY['UNITS'] * RES_PERCENT,
                                  run_as_root=True).AndReturn(('', ''))
        conn = openvz_conn.OpenVzConnection(False)
        self.mox.StubOutWithMock(conn, 'utility')
        conn.utility = UTILITY
        self.mox.ReplayAll()
        conn._set_cpuunits(INSTANCE, RES_PERCENT)

    def test_set_cpuunits_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', INSTANCE['id'], '--save',
                                  '--cpuunits',
                                  UTILITY['UNITS'] * RES_PERCENT,
                                  run_as_root=True) \
                                 .AndRaise(exception.ProcessExecutionError)
        conn = openvz_conn.OpenVzConnection(False)
        self.mox.StubOutWithMock(conn, 'utility')
        conn.utility = UTILITY
        self.mox.ReplayAll()
        self.assertRaises(exception.Error, conn._set_cpuunits,
                          INSTANCE, RES_PERCENT)

    def test_set_cpulimit_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', INSTANCE['id'], '--save',
                                  '--cpulimit',
                                  UTILITY['CPULIMIT'] * RES_PERCENT,
                                  run_as_root=True).AndReturn(('', ''))
        conn = openvz_conn.OpenVzConnection(False)
        self.mox.StubOutWithMock(conn, 'utility')
        conn.utility = UTILITY
        self.mox.ReplayAll()
        conn._set_cpulimit(INSTANCE, RES_PERCENT)

    def test_set_cpulimit_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', INSTANCE['id'], '--save',
                                  '--cpulimit',
                                  UTILITY['CPULIMIT'] * RES_PERCENT,
                                  run_as_root=True)\
                                  .AndRaise(exception.ProcessExecutionError)
        conn = openvz_conn.OpenVzConnection(False)
        self.mox.StubOutWithMock(conn, 'utility')
        conn.utility = UTILITY
        self.mox.ReplayAll()
        self.assertRaises(exception.Error, conn._set_cpulimit, INSTANCE,
                          RES_PERCENT)

    def test_set_cpus_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', INSTANCE['id'], '--save',
                                  '--cpus', mox.IgnoreArg(), run_as_root=True)\
                                  .AndReturn(('', ''))
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        conn._set_cpus(INSTANCE, VCPUS)

    def test_set_cpus_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', INSTANCE['id'], '--save',
                                  '--cpus', mox.IgnoreArg(), run_as_root=True)\
                                  .AndRaise(exception.ProcessExecutionError)
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        self.assertRaises(exception.Error, conn._set_cpus,
                          INSTANCE, VCPUS)

    def test_calc_pages_success(self):
        # this test is a little sketchy because it is testing the default
        # values of memory for instance type id 1.  if this value changes then
        # we will have a mismatch.

        # TODO(imsplitbit): make this work better.  This test is very brittle
        # because it relies on the default memory size for flavor 1 never
        # changing.  Need to fix this.
        conn = openvz_conn.OpenVzConnection(False)
        self.assertEqual(conn._calc_pages(MEMORYMB), MEM_PAGES)

    def test_get_cpuunits_capability_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzcpucheck', run_as_root=True).AndReturn(
                (CPUCHECKNOCONT, ''))
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        conn._get_cpuunits_capability()

    def test_get_cpuunits_capability_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzcpucheck', run_as_root=True).AndRaise(
            exception.ProcessExecutionError)
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        self.assertRaises(exception.Error, conn._get_cpuunits_capability)

    def test_get_cpuunits_usage_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzcpucheck', '-v', run_as_root=True)\
                                  .AndReturn((CPUCHECKCONT, ''))
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        conn._get_cpuunits_usage()

    def test_get_cpuunits_usage_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzcpucheck', '-v', run_as_root=True)\
                                  .AndRaise(exception.ProcessExecutionError)
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        self.assertRaises(exception.Error, conn._get_cpuunits_usage)

    def test_percent_of_resource(self):
        conn = openvz_conn.OpenVzConnection(False)
        self.mox.StubOutWithMock(conn, 'utility')
        conn.utility = UTILITY
        self.mox.ReplayAll()
        self.assertEqual(float, type(conn._percent_of_resource(MEMORYMB)))

    def test_get_memory_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('cat', '/proc/meminfo', run_as_root=True)\
                                  .AndReturn((MEMINFO, ''))
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        conn._get_memory()
        self.assertEquals(int, type(conn.utility['MEMORY_MB']))
        self.assertTrue(conn.utility['MEMORY_MB'] > 0)

    def test_get_memory_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('cat', '/proc/meminfo', run_as_root=True)\
                                  .AndRaise(exception.ProcessExecutionError)
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        self.assertRaises(exception.Error, conn._get_memory)

    def test_set_ioprio_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', INSTANCE['id'], '--save',
                                  '--ioprio', 3, run_as_root=True)\
                                  .AndReturn(('', None))
        conn = openvz_conn.OpenVzConnection(False)
        self.mox.StubOutWithMock(conn, '_percent_of_resource')
        conn._percent_of_resource(INSTANCE).AndReturn(.50)
        self.mox.ReplayAll()
        conn._set_ioprio(INSTANCE)

    def test_set_ioprio_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', INSTANCE['id'], '--save',
                                  '--ioprio', 3, run_as_root=True)\
                                  .AndRaise(exception.ProcessExecutionError)
        conn = openvz_conn.OpenVzConnection(False)
        self.mox.StubOutWithMock(conn, '_percent_of_resource')
        conn._percent_of_resource(INSTANCE).AndReturn(.50)
        self.mox.ReplayAll()
        self.assertRaises(exception.Error, conn._set_ioprio, INSTANCE)

    def test_set_diskspace_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', INSTANCE['id'], '--save',
                                  '--diskspace', mox.IgnoreArg(),
                                  run_as_root=True).AndReturn(('', None))
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        conn._set_diskspace(INSTANCE)

    def test_set_diskspace_soft_manual_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', INSTANCE['id'], '--save',
                                  '--diskspace', '40G:44G', run_as_root=True)\
                                  .AndReturn(('', None))
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        conn._set_diskspace(INSTANCE, 40)

    def test_set_diskspace_soft_and_hard_manual_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', INSTANCE['id'],
                                  '--save', '--diskspace', '40G:50G',
                                  run_as_root=True).AndReturn(('', None))
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        conn._set_diskspace(INSTANCE, 40, 50)

    def test_set_diskspace_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', INSTANCE['id'], '--save',
                                  '--diskspace', mox.IgnoreArg(),
                                  run_as_root=True)\
                                  .AndRaise(exception.ProcessExecutionError)
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        self.assertRaises(exception.Error, conn._set_diskspace, INSTANCE)

    def test_attach_volumes_success(self):
        conn = openvz_conn.OpenVzConnection(False)
        self.mox.StubOutWithMock(conn, 'attach_volume')
        conn.attach_volume(INSTANCE['name'], None,
                                      mox.IgnoreArg())
        self.mox.ReplayAll()
        conn._attach_volumes(INSTANCE)

    def test_attach_volume_success(self):
        self.mox.StubOutWithMock(openvz_conn.context, 'get_admin_context')
        openvz_conn.context.get_admin_context()
        self.mox.StubOutWithMock(openvz_conn.db, 'instance_get')
        openvz_conn.db.instance_get(mox.IgnoreArg(),
                                    INSTANCE['id']).AndReturn(
            INSTANCE)
        conn = openvz_conn.OpenVzConnection(False)
        self.mox.StubOutWithMock(conn, '_find_by_name')
        conn._find_by_name(INSTANCE['name']).AndReturn(INSTANCE)
        mock_volumes = self.mox.CreateMock(openvz_conn.OVZVolumes)
        mock_volumes.setup()
        mock_volumes.attach()
        mock_volumes.write_and_close()
        self.mox.StubOutWithMock(openvz_conn, 'OVZVolumes')
        openvz_conn.OVZVolumes(INSTANCE['id'], mox.IgnoreArg(),
                               mox.IgnoreArg(), mox.IgnoreArg()).AndReturn(
            mock_volumes)
        self.mox.ReplayAll()
        conn.attach_volume(INSTANCE['name'], '/dev/sdb1', '/var/tmp')

    def test_detach_volume_success(self):
        self.mox.StubOutWithMock(openvz_conn.context, 'get_admin_context')
        openvz_conn.context.get_admin_context()
        self.mox.StubOutWithMock(openvz_conn.db, 'instance_get')
        openvz_conn.db.instance_get(mox.IgnoreArg(), INSTANCE['id']).AndReturn(
            INSTANCE)
        conn = openvz_conn.OpenVzConnection(False)
        self.mox.StubOutWithMock(conn, '_find_by_name')
        conn._find_by_name(INSTANCE['name']).AndReturn(INSTANCE)
        mock_volumes = self.mox.CreateMock(openvz_conn.OVZVolumes)
        mock_volumes.setup()
        mock_volumes.detach()
        mock_volumes.write_and_close()
        self.mox.StubOutWithMock(openvz_conn, 'OVZVolumes')
        openvz_conn.OVZVolumes(INSTANCE['id'],
                               mox.IgnoreArg()).AndReturn(mock_volumes)
        self.mox.ReplayAll()
        conn.detach_volume(INSTANCE['name'], '/var/tmp')

    def test_make_directory_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('mkdir', '-p', TEMPFILE, run_as_root=True) \
                                 .AndReturn(('', ''))
        self.mox.ReplayAll()
        fh = openvz_conn.OVZFile(TEMPFILE)
        fh.make_dir(TEMPFILE)

    def test_make_directory_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('mkdir', '-p', TEMPFILE, run_as_root=True)\
                                  .AndRaise(exception.ProcessExecutionError)
        self.mox.ReplayAll()
        fh = openvz_conn.OVZFile(TEMPFILE)
        self.assertRaises(exception.Error, fh.make_dir, TEMPFILE)

    def test_touch_file_success(self):
        fh = openvz_conn.OVZFile(TEMPFILE)
        self.mox.StubOutWithMock(fh, 'make_path')
        fh.make_path()
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('touch', TEMPFILE, run_as_root=True)\
                                  .AndReturn(('', ''))
        self.mox.ReplayAll()
        fh.touch()

    def test_touch_file_failure(self):
        fh = openvz_conn.OVZFile(TEMPFILE)
        self.mox.StubOutWithMock(fh, 'make_path')
        fh.make_path()
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('touch', TEMPFILE, run_as_root=True)\
                                  .AndRaise(exception.ProcessExecutionError)
        self.mox.ReplayAll()
        self.assertRaises(exception.Error, fh.touch)

    def test_read_file_success(self):
        self.mox.StubOutWithMock(__builtin__, 'open')
        __builtin__.open(mox.IgnoreArg(), 'r').AndReturn(self.fake_file)
        self.mox.ReplayAll()
        fh = openvz_conn.OVZFile(TEMPFILE)
        fh.read()

    def test_read_file_failure(self):
        self.mox.StubOutWithMock(__builtin__, 'open')
        __builtin__.open(mox.IgnoreArg(), 'r').AndRaise(exception.Error)
        self.mox.ReplayAll()
        fh = openvz_conn.OVZFile(TEMPFILE)
        self.assertRaises(exception.Error, fh.read)

    def test_write_to_file_success(self):
        self.mox.StubOutWithMock(__builtin__, 'open')
        __builtin__.open(mox.IgnoreArg(), 'w').AndReturn(self.fake_file)
        self.mox.ReplayAll()
        fh = openvz_conn.OVZFile(TEMPFILE)
        fh.write()

    def test_write_to_file_failure(self):
        self.mox.StubOutWithMock(__builtin__, 'open')
        __builtin__.open(mox.IgnoreArg(), 'w').AndRaise(exception.Error)
        self.mox.ReplayAll()
        fh = openvz_conn.OVZFile(TEMPFILE)
        self.assertRaises(exception.Error, fh.write)

    def test_set_perms_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('chmod', 755, TEMPFILE, run_as_root=True)\
                                  .AndReturn(('', ''))
        self.mox.ReplayAll()
        fh = openvz_conn.OVZFile(TEMPFILE)
        fh.set_permissions(755)

    def test_set_perms_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('chmod', 755, TEMPFILE, run_as_root=True)\
                                  .AndRaise(exception.ProcessExecutionError)
        self.mox.ReplayAll()
        fh = openvz_conn.OVZFile(TEMPFILE)
        self.assertRaises(exception.Error, fh.set_permissions, 755)

    def test_gratuitous_arp_all_addresses(self):
        conn = openvz_conn.OpenVzConnection(False)
        self.mox.StubOutWithMock(conn, '_send_garp')
        conn._send_garp(INSTANCE['id'],
                        mox.IgnoreArg(),
                        mox.IgnoreArg()).MultipleTimes()
        self.mox.ReplayAll()
        conn._gratuitous_arp_all_addresses(INSTANCE, NETWORKINFO)

    def test_send_garp_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'exec2', INSTANCE['id'], 'arping',
                                  '-q', '-c', '5', '-A', '-I',
                                  NETWORKINFO[0][0]['bridge_interface'],
                                  NETWORKINFO[0][1]['ips'][0]['ip'],
                                  run_as_root=True).AndReturn(('', ERRORMSG))
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        conn._send_garp(INSTANCE['id'], NETWORKINFO[0][1]['ips'][0]['ip'],
                        NETWORKINFO[0][0]['bridge_interface'])

    def test_send_garp_faiure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'exec2', INSTANCE['id'], 'arping',
                                  '-q', '-c', '5', '-A', '-I',
                                  NETWORKINFO[0][0]['bridge_interface'],
                                  NETWORKINFO[0][1]['ips'][0]['ip'],
                                  run_as_root=True)\
        .AndRaise(exception.ProcessExecutionError)
        self.mox.ReplayAll()
        conn = openvz_conn.OpenVzConnection(False)
        conn._send_garp(INSTANCE['id'], NETWORKINFO[0][1]['ips'][0]['ip'],
                        NETWORKINFO[0][0]['bridge_interface'])
    def test_ovz_network_bridge_driver_plug(self):
        self.mox.StubOutWithMock(
            openvz_conn.linux_net.LinuxBridgeInterfaceDriver,
            'ensure_vlan_bridge'
        )
        openvz_conn.linux_net.LinuxBridgeInterfaceDriver.ensure_vlan_bridge(
            mox.IgnoreArg(), mox.IgnoreArg(), mox.IgnoreArg()
        )
        self.mox.ReplayAll()
        driver = openvz_conn.OVZNetworkBridgeDriver()
        for network, mapping in NETWORKINFO:
            driver.plug(INSTANCE, network, mapping)

    def test_ovz_network_interfaces_add_success(self):
        self.mox.StubOutWithMock(openvz_conn.OVZNetworkFile, 'append')
        openvz_conn.OVZNetworkFile.append(mox.IgnoreArg()).MultipleTimes()
        self.mox.StubOutWithMock(openvz_conn.OVZNetworkFile, 'write')
        openvz_conn.OVZNetworkFile.write().MultipleTimes()
        self.mox.StubOutWithMock(openvz_conn.OVZNetworkFile, 'set_permissions')
        openvz_conn.OVZNetworkFile.set_permissions(
            mox.IgnoreArg()).MultipleTimes()
        self.mox.StubOutWithMock(__builtin__, 'open')
        __builtin__.open(mox.IgnoreArg()).AndReturn(StringIO(NETTEMPLATE))
        ifaces = openvz_conn.OVZNetworkInterfaces(INTERFACEINFO)
        self.mox.StubOutWithMock(ifaces, '_add_netif')
        ifaces._add_netif(INTERFACEINFO[0]['id'],
                          mox.IgnoreArg(),
                          mox.IgnoreArg(),
                          mox.IgnoreArg()).MultipleTimes()
        self.mox.StubOutWithMock(ifaces, '_set_nameserver')
        ifaces._set_nameserver(INTERFACEINFO[0]['id'], INTERFACEINFO[0]['dns'])
        self.mox.ReplayAll()
        ifaces.add()

    def test_ovz_network_interfaces_add_ip_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', INTERFACEINFO[0]['id'],
                                  '--save', '--ipadd',
                                  INTERFACEINFO[0]['address'],
                                  run_as_root=True).AndReturn(('', ''))
        self.mox.ReplayAll()
        ifaces = openvz_conn.OVZNetworkInterfaces(INTERFACEINFO)
        ifaces._add_ip(INTERFACEINFO[0]['id'], INTERFACEINFO[0]['address'])

    def test_ovz_network_interfaces_add_ip_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', INTERFACEINFO[0]['id'],
                                  '--save', '--ipadd',
                                  INTERFACEINFO[0]['address'],
                                  run_as_root=True)\
                                  .AndRaise(exception.ProcessExecutionError)
        self.mox.ReplayAll()
        ifaces = openvz_conn.OVZNetworkInterfaces(INTERFACEINFO)
        self.assertRaises(exception.Error, ifaces._add_ip,
                          INTERFACEINFO[0]['id'], INTERFACEINFO[0]['address'])

    def test_ovz_network_interfaces_add_netif(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', INTERFACEINFO[0]['id'],
                                  '--save', '--netif_add',
                                  '%s,,veth%s.%s,%s,%s' % (
                                      INTERFACEINFO[0]['name'],
                                      INTERFACEINFO[0]['id'],
                                      INTERFACEINFO[0]['name'],
                                      INTERFACEINFO[0]['mac'],
                                      INTERFACEINFO[0]['bridge']),
                                  run_as_root=True).AndReturn(('', ''))
        self.mox.ReplayAll()
        ifaces = openvz_conn.OVZNetworkInterfaces(INTERFACEINFO)
        ifaces._add_netif(
            INTERFACEINFO[0]['id'],
            INTERFACEINFO[0]['name'],
            INTERFACEINFO[0]['bridge'],
            INTERFACEINFO[0]['mac']
        )

    def test_filename_factory_debian_variant(self):
        ifaces = openvz_conn.OVZNetworkInterfaces(INTERFACEINFO)
        for filename in ifaces._filename_factory():
            self.assertFalse('//' in filename)

    def test_set_nameserver_success(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', INTERFACEINFO[0]['id'],
                                  '--save', '--nameserver',
                                  INTERFACEINFO[0]['dns'], run_as_root=True)\
                                  .AndReturn(('', ''))
        self.mox.ReplayAll()
        ifaces = openvz_conn.OVZNetworkInterfaces(INTERFACEINFO)
        ifaces._set_nameserver(INTERFACEINFO[0]['id'], INTERFACEINFO[0]['dns'])

    def test_set_nameserver_failure(self):
        self.mox.StubOutWithMock(openvz_conn.utils, 'execute')
        openvz_conn.utils.execute('vzctl', 'set', INTERFACEINFO[0]['id'],
                                  '--save', '--nameserver',
                                  INTERFACEINFO[0]['dns'], run_as_root=True)\
                                  .AndRaise(exception.ProcessExecutionError)
        self.mox.ReplayAll()
        ifaces = openvz_conn.OVZNetworkInterfaces(INTERFACEINFO)
        self.assertRaises(exception.Error, ifaces._set_nameserver,
                          INTERFACEINFO[0]['id'], INTERFACEINFO[0]['dns'])
