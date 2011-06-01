import unittest

from reddwarfclient import Dbaas
from nova import flags
from nova import utils
from proboscis import test
from tests.dbaas.containers import container_info
from tests.dbaas.containers import GROUP_START as CONTAINER_START
from tests.dbaas.containers import GROUP_TEST

dns_driver = None
entry_factory = None
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
    """Creates the DNS Driver and entry factory used in subsequent tests."""

    def test_create_rs_dns_driver(self):
        global dns_driver
        dns_driver = utils.import_object(FLAGS.dns_driver)
        global entry_factory
        entry_factory = utils.import_object(FLAGS.dns_instance_entry_factory)
#        from collections import namedtuple
#        AuthUser = namedtuple("AuthUser", "auth_user")
#        container_info.user = AuthUser("admin")
#        container_info.id = 2


@test(depends_on_classes=[Setup],
      depends_on_groups=[CONTAINER_START],
      groups=[GROUP, GROUP_TEST],
      ignore=IGNORE)
class ConfirmDns(unittest.TestCase):
    """Make sure the DNS name was provisioned.

    This class actually calls the DNS driver to confirm the entry that should
    exist for the given container does exist.

    """

    def test_dns_entry_exists(self):
        global dns_driver
        instance = {'user_id':container_info.user.auth_user,
                    'id':str(container_info.id)}
        entry = entry_factory.create_entry(instance)
        entries = dns_driver.get_entries_by_name(entry.name)
        if len(entries) < 1:
            self.fail("Did not find name " + entry.name + \
                      " in the entries, which were as follows:"
                      + str(dns_driver.get_entries()))
        self.assertTrue(len(entries) > 0)