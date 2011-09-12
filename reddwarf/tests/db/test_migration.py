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
import migrate
import unittest


from nova import flags
from nova.db import migration as nova_migration
from reddwarf.db import migration

sql_connection = "sqlite:///reddwarf_test.sqlite"
current_version = 2


FLAGS = flags.FLAGS
FLAGS.Reset()
FLAGS['sql_connection'].SetDefault(sql_connection)


class DBMigrationTest(unittest.TestCase):
    """Test various Database migration scenarios"""

    def test0_nova_db_sync(self):
        nova_migration.db_sync()

    def test1_db_sync(self):
        version = migration.db_sync(sql_connection)
        self.assertEqual(int(version), current_version)

    def test2_db_version(self):
        version = migration.db_version(sql_connection)
        self.assertEqual(int(version), current_version)

    def test3_db_downgrade(self):
        dversion = 0
        version = migration.db_downgrade(sql_connection, dversion)
        self.assertEqual(int(version), dversion)

    def test4_db_upgrade(self):
        uversion = 1
        version = migration.db_upgrade(sql_connection, uversion)
        self.assertEqual(int(version), uversion)

    def test5_db_downgrade_invalid(self):
        invalid_version = "dfgd"
        try:
            migration.db_downgrade(sql_connection, invalid_version)
            self.assertFalse(True)
        except ValueError as err:
            self.assertEqual(err.args[0], "Invalid version '%s'"
                                % invalid_version)

    def test5_db_upgrade_invalid(self):
        invalid_version = "afsdf"
        try:
            migration.db_upgrade(sql_connection, invalid_version)
            self.assertFalse(True)
        except ValueError as err:
            self.assertEqual(err.args[0], "Invalid version '%s'"
                                % invalid_version)

    def test5_db_upgrade_to_lower_version(self):
        migration.db_sync(sql_connection)
        version = 0
        try:
            migration.db_upgrade(sql_connection, version)
            self.assertFalse(True)
        except migrate.exceptions.KnownError:
            self.assertTrue(True)

    def test5_db_downgrade_to_higher_version(self):
        migration.db_downgrade(sql_connection, 0)
        version = 1
        try:
            migration.db_downgrade(sql_connection, version)
            self.assertFalse(True)
        except migrate.exceptions.KnownError:
            self.assertTrue(True)
