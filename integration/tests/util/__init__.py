# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright (c) 2011 OpenStack, LLC.
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

"""
:mod:`tests` -- Utility methods for tests.
===================================

.. automodule:: utils
   :platform: Unix
   :synopsis: Tests for Nova.
.. moduleauthor:: Nirmal Ranganathan <nirmal.ranganathan@rackspace.com>
.. moduleauthor:: Tim Simpson <tim.simpson@rackspace.com>
"""


import re
import subprocess

from novaclient.v1_1.client import Client
from sqlalchemy import create_engine

from nova import flags
from nova import utils
from nose.tools import assert_false
from nova.utils import PollTimeOut
from reddwarfclient import Dbaas
from tests.util import test_config
from tests.util.client import TestClient as TestClient
from tests.util.topics import hosts_up


FLAGS = flags.FLAGS


_dns_entry_factory = None
def get_dns_entry_factory():
    """Returns a DNS entry factory."""
    global _dns_entry_factory
    if not _dns_entry_factory:
        class_name = FLAGS.dns_instance_entry_factory
        _dns_entry_factory = utils.import_object(class_name)
    return _dns_entry_factory

entry_factory = utils.import_object(FLAGS.dns_instance_entry_factory)


def check_database(container_id, dbname):
    """Checks if the name appears in a container's list of databases."""
    default_db = re.compile("[\w\n]*%s[\w\n]*" % dbname)
    dblist, err = process("sudo vzctl exec %s \"mysql -e 'show databases';\""
                            % container_id)
    if err:
        raise RuntimeError(err)
    if default_db.match(dblist):
        return True
    else:
        return False


def count_message_occurrence_in_logs(msg):
    """Counts the number of times some message appears in the log."""
    count = 0
    with open(FLAGS.logfile, 'r') as log:
        for line in log:
            if msg in line:
                count = count + 1
    return count


def check_logs_for_message(msg):
    """Searches the logs for the given message. Takes a long time."""
    with open(FLAGS.logfile, 'r') as logs:
        return msg in logs.read()


def count_notifications(priority, event_type):
    """Counts the number of times an ops notification has been given."""
    log_msg = priority + " nova.notification." + event_type
    return count_message_occurrence_in_logs(log_msg)


def create_dbaas_client(user):
    """Creates a rich client for the RedDwarf API using the test config."""
    test_config.nova.ensure_started()
    dbaas = Dbaas(user.auth_user, user.auth_key,
                  user.tenant, test_config.reddwarf_auth_url)
    dbaas.authenticate()
    return dbaas


def create_dns_entry(user_name, container_id):
    """Given the container_Id and it's owner returns the DNS entry."""
    instance = {'user_id':user_name,
                    'id':str(container_id)}
    entry_factory = get_dns_entry_factory()
    entry = entry_factory.create_entry(instance)
    # There is a lot of test code which calls this and then, if the entry
    # is None, does nothing. That's actually how the contract for this class
    # works. But we want to make sure that if the RsDnsDriver is defined in the
    # flags we are returning something other than None and running those tests.
    if should_run_rsdns_tests():
        assert_false(entry is None, "RsDnsDriver needs real entries.")
    return entry


def create_openstack_client(user):
    """Creates a rich client for the OpenStack API using the test config."""
    test_config.nova.ensure_started()
    openstack = Client(user.auth_user, user.auth_key,
                       user.tenant, test_config.nova_auth_url)
    openstack.authenticate()
    return openstack


def create_test_client(user):
    """Creates a test client loaded with asserts that works with both APIs."""
    os_client = create_openstack_client(user)
    dbaas_client = create_dbaas_client(user)
    assert dbaas_client.client.auth_token is not None
    return TestClient(dbaas_client=dbaas_client, os_client=os_client)


def init_engine(user, password, host):
    return create_engine("mysql://%s:%s@%s:3306" %
                               (user, password, host),
                               pool_recycle=1800, echo=True)


def process(cmd):
    process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
    result = process.communicate()
    return result


def restart_compute_service(extra_args=None):
    extra_args = extra_args or []
    test_config.compute_service.restart(extra_args=extra_args)
    # Be absolutely certain the compute manager is ready before passing control
    # back to caller.
    utils.poll_until(lambda: hosts_up('compute'),
                     sleep_time=1, time_out=60)
    pid = test_config.compute_service.find_proc_id()
    line = "Creating Consumer connection for Service compute from (pid=%d)" % \
           pid
    try:
        utils.poll_until(lambda: check_logs_for_message(line),
                         sleep_time=1, time_out=60)
    except PollTimeOut:
        raise RuntimeError("Could not find the line %s in the logs." % line)


def should_run_rsdns_tests():
    """If true, then the RS DNS tests should also be run."""
    return FLAGS.dns_driver == "nova.dns.rsdns.driver.RsDnsDriver"


def string_in_list(str, substr_list):
    """Returns True if the string appears in the list."""
    return any([str.find(x) >=0 for x in substr_list])


def get_vz_ip_for_device(container_id, device):
    """Get the IP of the device within openvz for the specified container"""
    ip, err = process("""sudo vzctl exec %(container_id)s ifconfig %(device)s"""
                      """ | awk '/inet addr/{gsub(/addr:/,"");print $2}'"""
                      % locals())
    if err:
        self.assertFalse(True, err)
    else:
        return ip.strip()
