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
import sys
import time
import unittest
from proboscis import test
from proboscis.decorators import expect_exception

import rsdns
from rsdns import driver as drivermod
from rsdns.driver import RsDnsDriver
from rsdns.driver import RsDnsZone
from rsdns.driver import DnsEntry

driver = None

DEFAULT_ZONE = RsDnsZone(1, "dbaas.rackspace.org")
TEST_CONTENT="126.1.1.1"
TEST_NAME="hiwassup.dbaas.rackspace.org"


def create_domain_if_needed():
    if rsdns.ADD_DOMAINS:
        driver.dns_client.domains.create(driver.default_dns_zone.name)
    else:
        self.fail("Could not find default dns zone.")


@test(groups=["ignore"], enabled=False)
class RandomClientTests(unittest.TestCase):
    """Random tests using the client. Useful for finding how the API works."""

    def setUp(self):
        set_test_flags()

    def test_zone(self):
        global driver
        drivermod.FLAGS.dns_domain_id = 1
        driver = RsDnsDriver()
        client = driver.dns_client
        hostname = "blueparrakars.com"
        future = client.domains.create(hostname)
        while not future.ready:
            import time
            time.sleep(1)
        domain = future.resource
        domains = client.domains.list()
        domain = None
        for d in domains:
            if d.name == hostname:
                domain = d
        self.assertNotEqual(None, domain)

        record_future = client.records.create(domain, "admin-1." + hostname,
                                              "128.1.1.1", "A", 300)
        while not record_future.ready:
            import time
            time.sleep(1)
        record = record_future.resource
        self.assertEqual("admin-1." + hostname, record.name)


@test(groups=["rsdns.domains"])
class ConfirmDomainIsValid(unittest.TestCase):
    """Makes sure the domain (specified by the FLAG settings) is valid."""

    def test_zone(self):
        global driver
        driver = RsDnsDriver(raise_if_zone_missing=False)
        self.assertNotEqual(None, driver.default_dns_zone)
        def zone_found():
            zones = driver.get_dns_zones()
            for zone in zones:
                if zone.name == driver.default_dns_zone.name:
                    driver.default_dns_zone.id = zone.id
                    return True
            return False
        if zone_found():
            return
        create_domain_if_needed()
        for i in range(5):
            if zone_found():
                return
        self.fail("""Could not find default dns zone.
                  This happens when they clear the staging DNS service of data.
                  To fix it, manually run the tests as follows:
                  $ ADD_DOMAINS=True python run_tests.py
                  and if all goes well the tests will create a new domain
                  record.""")


@test(depends_on_classes=[ConfirmDomainIsValid], groups=["show_entries",
                                                         "rsdns.domains"])
class AtFirstNoEntriesExist(unittest.TestCase):
    """Assert no entries with given names exist before proceeding."""

    def setUp(self):
        list = driver.get_entries_by_name(name=TEST_NAME)
        for entry in list:
            driver.delete_entry(name=entry.name, type=entry.type,
                                dns_zone=entry.dns_zone)
        
    def test_10_create_entry(self):
        list = driver.get_entries_by_name(name=TEST_NAME)
        self.assertEqual(0, len(list))


@test(depends_on_classes=[AtFirstNoEntriesExist], groups=["rsdns.domains"])
class WhenCreatingAWellFormedEntry(unittest.TestCase):
    """Create an entry with the driver and assert it can be retrieved."""

    def test_10_create_entry(self):
        fullname = TEST_NAME
        entry = DnsEntry(name=fullname, content=TEST_CONTENT, type="A",
                         ttl=3600)
        driver.create_entry(entry)
        list = None
        for i in range(5):
            list = driver.get_entries_by_name(name=fullname)
            if len(list) > 1:
                break
            time.sleep(1)
        self.assertEqual(1, len(list))
        list2 = driver.get_entries_by_content(content=TEST_CONTENT)
        self.assertEqual(1, len(list2))

    def test_20_create_entry(self):
        fullname = TEST_NAME
        driver.delete_entry(fullname, "A")


@test(groups=["rsdns.show_entries"],
      depends_on=[ConfirmDomainIsValid],
      enabled=os.environ.get("SHOW_DNS_ENTRIES", 'False') == 'True')
def get_entries_by_name():
    """This just shows the current entries in case you're curious."""
    import sys
    def msg(text):
        sys.__stdout__.write(str(text) + "\n")
    entries = driver.get_entries() #_by_name("admin-1")
    msg("Showing all DNS entries:")
    for entry in entries:
        msg(entry)
