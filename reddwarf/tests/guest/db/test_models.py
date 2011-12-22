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

from nova import test
from reddwarf.guest.db.models import MySQLDatabase
from reddwarf.guest.db.models import MySQLUser


class MySQLDatabaseTest(test.TestCase):

    dbname = "testdb? #@DT23-_"

    def test_name_only(self):
        mydb = MySQLDatabase()
        try:
            mydb.name = self.dbname
        except ValueError as e:
            self.assertFalse(True, msg=e)

        self.assertEqual(mydb.name, self.dbname)
        self.assertEqual(mydb.character_set, MySQLDatabase.__charset__)
        self.assertEqual(mydb.collate, MySQLDatabase.__collation__)

    def test_name_length(self):
        mydb = MySQLDatabase()
        long_64_dbname = "abfadklfgklq3u4q78tzdfjhvgajkdshfgjaef72346JKVFEJSHr38475adsgfd4"
        long_dbname = "abfadklfgklq3u4q78tzdfjhvgajkdshfgjaef72346JKVFEJSHr38475adsgfd4s"
        try:
            mydb.name = long_64_dbname
            self.assertTrue(True)
        except ValueError as e:
            self.assertFalse(True, msg=e)
        try:
            mydb.name = long_dbname
            self.assertFalse(True)
        except ValueError as e:
            self.assertEquals(e.args[0],
                              "Database name '%s' is too long. Max length = 64"
                              % long_dbname)

    def test_ser_der(self):
        mydb = MySQLDatabase()
        der_mydb = MySQLDatabase()
        try:
            mydb.name = self.dbname
            mydb.charset = "latin1"
            mydb.charset = "latin1_general_ci"
            json = mydb.serialize()

            der_mydb.deserialize(json)
        except ValueError as e:
            self.assertFalse(True, msg=e)
        self.assertEqual(mydb.name, der_mydb.name)
        self.assertEqual(mydb.character_set, der_mydb.character_set)
        self.assertEqual(mydb.collate, der_mydb.collate)

    def test_default_collation(self):
        char = "latin2"
        coll = "latin2_general_ci"
        mydb = MySQLDatabase()
        try:
            mydb.name = self.dbname
            mydb.character_set = char
        except ValueError as e:
            self.assertFalse(True, msg=e)

        self.assertEquals(mydb.character_set, char)
        self.assertEquals(mydb.collate, coll)

    def test_matching_charset(self):
        coll = "ujis_bin"
        char = "ujis"
        mydb = MySQLDatabase()
        try:
            mydb.name = self.dbname
            mydb.collate = coll
        except ValueError as e:
            self.assertFalse(True, msg=e)

        self.assertEquals(mydb.character_set, char)
        self.assertEquals(mydb.collate, coll)

    def test_invalid_charset(self):
        invalid_char = "cp1250_croatian_ci"
        mydb = MySQLDatabase()
        try:
            mydb.name = self.dbname
            mydb.character_set = invalid_char
            self.assertFalse(True)
        except ValueError as e:
            self.assertEquals(e.args[0],
                        "'%s' not a valid character set" % invalid_char)

    def test_invalid_collate(self):
        invalid_coll = "greek"
        mydb = MySQLDatabase()
        try:
            mydb.name = self.dbname
            mydb.collate = invalid_coll
            self.assertFalse(True)
        except ValueError as e:
            self.assertEquals(e.args[0],
                              "'%s' not a valid collation" % invalid_coll)

    def test_invalid_dbname(self):
        self._test_invalid_name("te!@#%'$3")

    def test_dbname_with_backslash(self):
        self._test_invalid_name("db\name")

    def test_name_with_starting_space(self):
        self._test_invalid_name(" testdb")

    def test_name_with_ending_space(self):
        self._test_invalid_name("testdb ")

    def test_name_with_starting_question(self):
        self._test_invalid_name("?testdb")

    def test_name_with_ending_question(self):
        self._test_invalid_name("testdb?")

    def test_name_with_starting_hash(self):
        self._test_invalid_name("#testdb")

    def test_name_with_ending_hash(self):
        self._test_invalid_name("testdb#")

    def test_name_with_starting_at(self):
        self._test_invalid_name("@testdb")

    def test_name_with_ending_at(self):
        self._test_invalid_name("testdb@")

    def _test_invalid_name(self, name):
        mydb = MySQLDatabase()
        try:
            mydb.name = name
            self.assertFalse(True)
        except ValueError as e:
            self.assertEquals(e.args[0],
                    "'%s' is not a valid database name" % name)

    def test_not_matching_charset_collate(self):
        char = "latin1"
        coll = "latin2_croatian_ci"
        mydb = MySQLDatabase()
        try:
            mydb.name = self.dbname
            mydb.character_set = char
            mydb.collate = coll
            self.assertFalse(True)
        except ValueError as e:
            self.assertEquals(e.args[0],
                "'%s' not a valid collation for charset '%s'" % (coll, char))

    def test_all_valid_charset_collate_pairs(self):
        mydb = MySQLDatabase()

        try:
            for coll, char in MySQLDatabase.collation.items():
                mydb.character_set = char
                mydb.collate = coll
            pass
        except  ValueError as e:
            self.assertFalse(True, msg=e)


class MySQLUserTest(test.TestCase):

    invalid_list = [" te!$3", "te!$3 ", "t'e!$3", "\"te!$3",
                    ";te!$3", "t`e!$3", "te,!$3", "t/e!$3",
                    "t\n!$3", "t\\n!$3", "t\e!$3"]

    def test_valid_name_pwd(self):
        name = "test02"
        passwd = "pass$*%^"
        dbname = "testdb"
        myuser = MySQLUser()
        try:
            myuser.name = name
            myuser.password = passwd
            myuser.databases = dbname
        except ValueError as e:
            self.assertFalse(True, e)

        self.assertEqual(myuser.name, name)
        self.assertEqual(myuser.password, passwd)
        self.assertEqual(myuser.databases[0]['_name'], dbname)

    def test_name_length(self):
        myuser = MySQLUser()

        validname = "afaasdnkaksdfdfg"
        longname = "afaasdnkaksdfdfg2"

        try:
            myuser.name = validname
            self.assertTrue(True)
        except ValueError as e:
            self.assertFalse(True, e)
        try:
            myuser.name = longname
            self.assertFalse(True)
        except ValueError as e:
            self.assertEquals(e.args[0],
                              "User name '%s' is too long. Max length = 16"
                              % longname)

    def test_ser_der(self):
        myuser = MySQLUser()
        der_myuser = MySQLUser()
        try:
            myuser.name = "!@#$%^&*()_"
            myuser.password = "-+=:.<>?~"
            myuser.databases = "sambpleadsf"
            json = myuser.serialize()

            der_myuser.deserialize(json)
        except ValueError as e:
            self.assertFalse(True, e)
        self.assertEqual(myuser.name, der_myuser.name)
        self.assertEqual(myuser.password, der_myuser.password)
        self.assertEquals(myuser.databases, der_myuser.databases)

    def test_invalid_username(self):
        for name in self.invalid_list:
            self._invalid_user_name(name)

    def _invalid_user_name(self, name):
        myuser = MySQLUser()
        try:
            myuser.name = name
            self.assertFalse(True, name)
        except ValueError as e:
            self.assertEquals(e.args[0],
                    "'%s' is not a valid user name" % name)

    def test_invalid_password(self):
        for password in self.invalid_list:
            self._invalid_password(password)

    def _invalid_password(self, password):
        myuser = MySQLUser()
        try:
            myuser.password = password
            self.assertFalse(True, password)
        except ValueError as e:
            self.assertEquals(e.args[0],
                    "'%s' is not a valid password" % password)
