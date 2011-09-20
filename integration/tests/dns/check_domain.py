# Copyright 2011 OpenStack LLC.
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
"""Checks that the domain specified in the flag file exists and is valid.

If you define the environment variable ADD_DOMAINS=True when running the tests,
they will create the domain if its not found (see below for details).

"""
import os
import time
import unittest
from nova import utils
from nova.dns.rsdns.driver import create_client_with_flag_values
from nova import flags
from proboscis import test
from proboscis import before_class
from proboscis.asserts import assert_equal
from proboscis.asserts import assert_not_equal
from proboscis.decorators import expect_exception
from proboscis.decorators import time_out

import rsdns
from nova.dns.driver import DnsEntry
from nova.dns.rsdns.driver import RsDnsDriver
from nova.dns.rsdns.driver import RsDnsZone

FLAGS = flags.FLAGS
TEST_CONTENT="126.1.1.1"
TEST_NAME="hiwassup.%s" % FLAGS.dns_domain_name


@test(groups=["rsdns.domains", "rsdns.show_entries"])
class ClientTests(object):

    @before_class
    def replace_logging(self):
        import httplib2
        httplib2.debuglevel = 1
#        from rsdns.client import dns_client
#        class FakeLog(object):
#            def debug(self, msg):
#                print(msg)
#        dns_client.LOG = FakeLog()
        pass

    @test
    def can_auth(self):
        self.client = create_client_with_flag_values()
        self.client.authenticate()

    @test(depends_on=[can_auth])
    def list_domains(self):
        domains = self.client.domains.list()
        print(domains)


@test(groups=["rsdns.domains"], depends_on=[ClientTests])
class RsDnsDriverTests(object):
    """Tests the RS DNS Driver."""

    def create_domain_if_needed(self):
        """Adds the domain specified in the flags."""
        print("Creating domain %s" % self.driver.default_dns_zone.name)
        future = self.driver.dns_client.domains.create(
            self.driver.default_dns_zone.name)
        while not future.ready:
            time.sleep(2)
        print("Got something: %s" % future.resource)
        print("The domain should have been created.")

    @test
    @time_out(2 * 60)
    def ensure_domain_specified_in_flags_exists(self):
        """Make sure the domain in the FLAGS exists."""
        self.driver = RsDnsDriver(raise_if_zone_missing=False)
        assert_not_equal(None, self.driver.default_dns_zone)
        def zone_found():
            zones = self.driver.get_dns_zones()
            print("Retrieving zones.")
            for zone in zones:
                print("zone %s" % zone)
                if zone.name == self.driver.default_dns_zone.name:
                    self.driver.default_dns_zone.id = zone.id
                    return True
            return False
        if zone_found():
            return
        self.create_domain_if_needed()
        for i in range(5):
            if zone_found():
                return
        self.fail("""Could not find default dns zone.
                  This happens when they clear the staging DNS service of data.
                  To fix it, manually run the tests as follows:
                  $ ADD_DOMAINS=True python int_tests.py
                  and if all goes well the tests will create a new domain
                  record.""")

    @test(depends_on=[ensure_domain_specified_in_flags_exists],
          enabled=FLAGS.dns_domain_name != "dbaas.rackspace.com")
    def delete_all_entries(self):
        """Deletes all entries under the default domain."""
        list = self.driver.get_entries()
        for entry in list:
            self.driver.delete_entry(name=entry.name, type=entry.type,
                                     dns_zone=entry.dns_zone)
        # It takes awhile for them to be deleted.
        utils.poll_until(lambda : self.driver.get_entries_by_name(TEST_NAME),
                         lambda list : len(list) == 0,
                         sleep_time=4, time_out=60)

    @test(depends_on=[delete_all_entries])
    def create_test_entry(self):
        fullname = TEST_NAME
        entry = DnsEntry(name=fullname, content=TEST_CONTENT, type="A",
                         ttl=3600)
        self.driver.create_entry(entry)
        list = None
        for i in range(5):
            list = self.driver.get_entries_by_name(name=fullname)
            if len(list) > 1:
                break
            time.sleep(1)
        assert_equal(1, len(list))
        list2 = self.driver.get_entries_by_content(content=TEST_CONTENT)
        assert_equal(1, len(list2))

    @test(depends_on=[create_test_entry])
    def delete_test_entry(self):
        fullname = TEST_NAME
        self.driver.delete_entry(fullname, "A")
        # It takes awhile for them to be deleted.
        utils.poll_until(lambda : self.driver.get_entries_by_name(TEST_NAME),
                         lambda list : len(list) == 0,
                         sleep_time=2, time_out=60)
