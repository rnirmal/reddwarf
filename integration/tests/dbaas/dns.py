import unittest

from dbaas import Dbaas
from nova import flags
from nova import utils
from proboscis import test
from tests.dbaas.containers import container_info
from tests.dbaas.containers import GROUP_START as CONTAINER_START
from tests.dbaas.containers import GROUP_TEST

dns_driver = None
FLAGS = flags.FLAGS
FLAGS = flags.FLAGS
flags.DEFINE_string('dns_driver', 'nova.dns.driver.DnsDriver',
                    'Driver to use for DNS work')

GROUP = "dbaas.guest.dns"

IGNORE = False
try:
    import rsdns
except Exception:
    IGNORE = True


@test(groups=[GROUP, GROUP_TEST], ignore=IGNORE)
class Setup(unittest.TestCase):
    """Creates the client."""

    def test_create_rs_dns_driver(self):
        global dns_driver
        dns_driver = utils.import_object(FLAGS.dns_driver)


@test(depends_on_classes=[Setup],
      depends_on_groups=[CONTAINER_START],
      groups=[GROUP, GROUP_TEST],
      ignore=IGNORE)
class ConfirmDns(unittest.TestCase):

    def test_dns_entry_exists(self):
        global dns_driver
        name = container_info.user.auth_user + str(container_info.id)
        entries = dns_driver.get_entries_by_name(name)
        self.assertTrue(len(entries) > 0)