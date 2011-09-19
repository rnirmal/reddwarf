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
import os
import unittest


try:
    from migrate.exceptions import KnownError  # version > 0.7.0
except ImportError:
    from migrate.versioning.exceptions import KnownError


from nova import flags
from nova.db import migration as nova_migration
from reddwarf.db import migration

database_file = "reddwarf_test.sqlite"
sql_connection = "sqlite:///%s" % database_file
current_version = 4


FLAGS = flags.FLAGS
FLAGS.Reset()
FLAGS['sql_connection'].SetDefault(sql_connection)


class DBMigrationTest(unittest.TestCase):
    """Test various Database migration scenarios"""

    def test0_nova_db_sync(self):
        if os.path.exists(database_file):
            os.remove(database_file)
        nova_migration.db_sync()

    def test1_db_upgrade(self):
        migration.version_control(sql_connection)
        uversion = 2
        version = migration.db_upgrade(sql_connection, uversion)
        self.assertEqual(int(version), uversion)

    def test2_db_upgrade_to_lower_version(self):
        try:
            migration.db_upgrade(sql_connection, 0)
            self.assertFalse(True)
        except KnownError:
            self.assertTrue(True)

    def test3_db_downgrade(self):
        dversion = 0
        version = migration.db_downgrade(sql_connection, dversion)
        self.assertEqual(int(version), dversion)

    def test4_db_downgrade_to_higher_version(self):
        version = 1
        try:
            migration.db_downgrade(sql_connection, version)
            self.assertFalse(True)
        except KnownError:
            self.assertTrue(True)

    def test5_db_downgrade_invalid(self):
        invalid_version = "dfgd"
        try:
            migration.db_downgrade(sql_connection, invalid_version)
            self.assertFalse(True)
        except ValueError as err:
            self.assertEqual(err.args[0], "Invalid version '%s'"
                                % invalid_version)

    def test6_db_upgrade_invalid(self):
        invalid_version = "afsdf"
        try:
            migration.db_upgrade(sql_connection, invalid_version)
            self.assertFalse(True)
        except ValueError as err:
            self.assertEqual(err.args[0], "Invalid version '%s'"
                                % invalid_version)

    def test7_db_sync(self):
        version = migration.db_sync(sql_connection)
        self.assertEqual(int(version), current_version)

    def test8_db_version(self):
        version = migration.db_version(sql_connection)
        self.assertEqual(int(version), current_version)