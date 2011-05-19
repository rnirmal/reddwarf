import gettext
import os
import subprocess
import sys
import time
import re
import unittest

from sqlalchemy import create_engine
from sqlalchemy.sql.expression import text

#from dbaas import Dbaas
from dbaas import Dbaas
from novaclient.exceptions import NotFound
from proboscis import test
from tests.dbaas.containers import container_info
from tests.dbaas.containers import GROUP_START as CONTAINER_START
from tests.dbaas.containers import GROUP_TEST

dbaas = None
dns_driver = None
FLAGS = flags.FLAGS
success_statuses = ["build", "active"]

GROUP = "dbaas.guest.dns"

@test(groups=[GROUP])
class Setup(unittest.TestCase):
    """Creates the client."""

    def test_create_dbaas_client(self):
        """Sets up the client."""
        global dbaas
        dbaas = util.create_dbaas_client(container_info.user)

    def test_create_rs_dns_driver(self):
        global dns_driver
        dns_driver = FLAGS.dns_driver

@test(depends_on_classes=[Setup, CONTAINER_START], groups=[GROUP])
class ConfirmDns(unittest.TestCase):

    def test_dns_entry_exists(self, err):
       #TODO(tim.simpson): Check for the name somehow