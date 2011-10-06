import unittest

from nova.exception import AdminRequired
from proboscis import test
from proboscis.decorators import expect_exception
from tests import util
from tests.util.users import Requirements

"""
These tests verify that admin privileges are checked
when calling management level functions.
"""

@test(depends_on_classes=[Setup], groups=[GROUP_TEST, 'dbaas.admin_required'])
class TestAdminRequired(unittest.TestCase):
   """
   Test that the created instance has 2 nics with the specified ip
   address as allocated to it.
   """

   @test()
   def create_user_and_client(self):
      find_user = tests.util.test_config.users.find_user
      self.user = find_user(Requirements(is_admin=False))
      self.dbaas = util.create_dbaas_client(self.user)

   @test(depends_on=[create_users_and_client])
   @expect_exception(AdminRequired)
   def test_accounts_show(self):
      self.dbaas.accounts.show(0)

   @test(depends_on=[create_users_and_client])
   @expect_exception(AdminRequired)
   def test_guests_upgrade(self):
      self.dbaas.guests.upgrade(0)

   @test(depends_on=[create_users_and_client])
   @expect_exception(AdminRequired)
   def test_guests_upgradeall(self):
      self.dbaas.guests.upgradeall()

   @test(depends_on=[create_users_and_client])
   @expect_exception(AdminRequired)
   def test_hosts_index(self):
      self.dbaas.hosts.index()

   @test(depends_on=[create_users_and_client])
   @expect_exception(AdminRequired)
   def test_hosts_show(self):
      self.dbaas.hosts.show(0)

   @test(depends_on=[create_users_and_client])
   @expect_exception(AdminRequired)
   def test_mgmt_show(self):
      self.dbaas.management.show(0)

   @test(depends_on=[create_users_and_client])
   @expect_exception(AdminRequired)
   def test_mgmt_root_history(self):
      self.dbaas.management.root_enabled_hisotry(0)

   @test(depends_on=[create_users_and_client])
   @expect_exception(AdminRequired)
   def test_storage_index(self):
      self.dbaas.storage.index()