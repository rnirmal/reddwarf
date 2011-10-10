import unittest

from novaclient.exceptions import ClientException
from proboscis import test
from proboscis.decorators import expect_exception
from tests import util
from tests.dbaas.instances import GROUP_START
from tests.dbaas.instances import GROUP_TEST
from tests.util.users import Requirements


@test(depends_on_groups=[GROUP_START],
  groups=[GROUP_TEST, 'dbaas.admin_required'])
class TestAdminRequired(object):
   """
   These tests verify that admin privileges are checked
   when calling management level functions.
   """

   @test()
   def create_user_and_client(self):
      """ Create the user and client for use in the subsequent tests."""
      find_user = util.test_config.users.find_user
      self.user = find_user(Requirements(is_admin=False))
      self.dbaas = util.create_dbaas_client(self.user)

   @test(depends_on=[create_user_and_client])
   @expect_exception(ClientException)
   def test_accounts_show(self):
      """ A regular user may not view the details of any account. """
      self.dbaas.accounts.show(0)

   @test(depends_on=[create_user_and_client])
   @expect_exception(ClientException)
   def test_hosts_index(self):
      """ A regular user may not view the list of hosts. """
      self.dbaas.hosts.index()

   @test(depends_on=[create_user_and_client])
   @expect_exception(ClientException)
   def test_hosts_get(self):
      """ A regular user may not view the details of any host. """
      self.dbaas.hosts.get(0)

   @test(depends_on=[create_user_and_client])
   @expect_exception(ClientException)
   def test_mgmt_show(self):
      """ A regular user may not view the management details of any instance. """
      self.dbaas.management.show(0)

   @test(depends_on=[create_user_and_client])
   @expect_exception(ClientException)
   def test_mgmt_root_history(self):
      """
      A regular user may not view the root access history of
      any instance.
      """
      self.dbaas.management.root_enabled_history(0)

   @test(depends_on=[create_user_and_client])
   @expect_exception(ClientException)
   def test_storage_index(self):
      """ A regular user may not view the list of storage available. """
      self.dbaas.storage.index()