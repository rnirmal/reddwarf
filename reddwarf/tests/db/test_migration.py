#    Copyright 2011 OpenStack LLC
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
Tests for Database migration
"""
import unittest

try:
    from migrate.exceptions import KnownError  # version > 0.7.0
except ImportError:
    from migrate.versioning.exceptions import KnownError

from nova import flags
from reddwarf.db import migration
from reddwarf.tests import util
from reddwarf import tests as testinit


FLAGS = flags.FLAGS


class DBMigrationTest(unittest.TestCase):
    """Test various Database migration scenarios"""

    def test0_reset(self):
        util.reset_database()

    def test1_db_upgrade(self):
        migration.version_control()
        uversion = 2
        version = migration.db_upgrade(uversion)
        self.assertEqual(int(version), uversion)

    def test2_db_upgrade_to_lower_version(self):
        try:
            migration.db_upgrade(0)
            self.assertFalse(True)
        except KnownError:
            self.assertTrue(True)

    def test3_db_downgrade(self):
        dversion = 0
        version = migration.db_downgrade(dversion)
        self.assertEqual(int(version), dversion)

    def test4_db_downgrade_to_higher_version(self):
        version = 1
        try:
            migration.db_downgrade(version)
            self.assertFalse(True)
        except KnownError:
            self.assertTrue(True)

    def test5_db_downgrade_invalid(self):
        invalid_version = "dfgd"
        try:
            migration.db_downgrade(invalid_version)
            self.assertFalse(True)
        except ValueError as err:
            self.assertEqual(err.args[0], "Invalid version '%s'"
                                % invalid_version)

    def test6_db_upgrade_invalid(self):
        invalid_version = "afsdf"
        try:
            migration.db_upgrade(invalid_version)
            self.assertFalse(True)
        except ValueError as err:
            self.assertEqual(err.args[0], "Invalid version '%s'"
                                % invalid_version)

    def test7_db_sync(self):
        version = migration.db_sync()
        self.assertEqual(int(version), testinit.reddwarf_db_version)

    def test8_db_version(self):
        version = migration.db_version()
        self.assertEqual(int(version), testinit.reddwarf_db_version)
