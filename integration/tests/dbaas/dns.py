import time
import unittest

from proboscis import test
from proboscis.decorators import time_out

from reddwarfclient import Dbaas
from nova import flags
from nova import utils
import rsdns
from tests.dbaas.containers import container_info
from tests.dbaas.containers import GROUP_START as CONTAINER_START
from tests.dbaas.containers import GROUP_TEST
from tests.dbaas.containers import GROUP_STOP as CONTAINER_STOP

dns_driver = None

FLAGS = flags.FLAGS
GROUP = "dbaas.guest.dns"


@test(groups=[GROUP, GROUP_TEST])
class Setup(unittest.TestCase):
    """Creates the DNS Driver and entry factory used in subsequent tests."""

    def test_create_rs_dns_driver(self):
        global dns_driver
        dns_driver = utils.import_object(FLAGS.dns_driver)


@test(depends_on_classes=[Setup],
      depends_on_groups=[CONTAINER_START],
      groups=[GROUP, GROUP_TEST])
class WhenContainerIsCreated(unittest.TestCase):
    """Make sure the DNS name was provisioned.

    This class actually calls the DNS driver to confirm the entry that should
    exist for the given container does exist.

    """

    def test_dns_entry_should_exist(self):
        entry = container_info.expected_dns_entry()
        if entry:
            entries = dns_driver.get_entries_by_name(entry.name)
            if len(entries) < 1:
                self.fail("Did not find name " + entry.name + \
                          " in the entries, which were as follows:"
                          + str(dns_driver.get_entries()))
            self.assertTrue(len(entries) > 0)


@test(depends_on_classes=[Setup, WhenContainerIsCreated],
      depends_on_groups=[CONTAINER_STOP],
      groups=[GROUP])
class AfterContainerIsDestroyed(unittest.TestCase):
    """Make sure the DNS name is removed along with a container.

    Because the compute manager calls the DNS manager with RPC cast, it can
    take awhile.  So we wait for 30 seconds for it to disappear.

    """

    def test_dns_entry_exist_should_be_removed_shortly_thereafter(self):
        entry = container_info.expected_dns_entry()

        if not entry:
            return

        def get_entries():
            return dns_driver.get_entries_by_name(entry.name)

        try:
            utils.poll_until(get_entries, lambda entries : len(entries) == 0,
                             sleep_time=1, time_out=30)
        except utils.PollTimeOut:
            # Manually delete the rogue item
            dns_driver.delete_entry(entry.name, entry.type, entry.dns_zone)
            self.fail("The DNS entry was never deleted when the container "
                      "was destroyed.")
