import collections
import unittest
import httplib2
import mox

from novaclient import client
from novaclient import exceptions
from rsdns.client import DNSaasClient
from rsdns.client import RecordsManager


FakeDNSaaS = collections.namedtuple("FakeDNSaaS",
                                    ['client', 'domains', 'records'])


FAKE_DOMAIN_ID = 75762
FAKE_RECORD_ID = 48217


class DNSClientRecordPagination(unittest.TestCase):

    def setUp(self):
        self.mox = mox.Mox()

    def tearDown(self):
        self.mox.VerifyAll()

    def test_list(self):
        dns = FakeDNSaaS(None, None, None)
        records = RecordsManager(dns)
        # Create mocks of methods called by the list method.
        # Not the create_from_list is mocked out to return a list of letters
        # instead of record objects to make the test easier to write / read.
        self.mox.StubOutWithMock(records, "create_from_list")
        self.mox.StubOutWithMock(records, "match_record")
        self.mox.StubOutWithMock(records, "page_list")
        expected_url = "/domains/%s/records/%s" \
                       % (FAKE_DOMAIN_ID, FAKE_RECORD_ID)
        # page_list returns a list three times; the final time the offset
        # is None, which terminates the loop.
        records.page_list(expected_url + "?offset=0").AndReturn((['a', 'b'], 2))
        records.page_list(expected_url + "?offset=2")\
            .AndReturn((['c', 'd'], 4))
        records.page_list(expected_url + "?offset=4")\
            .AndReturn((['e'], None))
        expected_full_list = ['a', 'b', 'c', 'd', 'e']
        records.create_from_list(expected_full_list)\
            .AndReturn(expected_full_list)
        for letter in expected_full_list:
            records.match_record(letter, None, None, None)\
                .AndReturn(letter != 'c')
        self.mox.ReplayAll()

        # Actually call list method and make sure it calls methods as specified
        # above.
        actual_list = records.list(FAKE_DOMAIN_ID, FAKE_RECORD_ID)
        expected_filtered_list = list(expected_full_list)
        # Since match_record returned false for "c" it won't be in the final
        # list.
        del expected_filtered_list[2]
        self.assertEqual(len(expected_filtered_list), len(actual_list))
        for letter in expected_filtered_list:
            self.assertTrue(letter in actual_list)

    def test_page_list(self):
        """Tests grabbing the list and next offset from the RS DNS API."""
        client = self.mox.CreateMock(DNSaasClient)
        dns = FakeDNSaaS(client, None, None)
        dns.client.get("fake.com").AndReturn((None,
            {"records":[ 'a', 'b' ],
             "totalEntries":4,
             "links":[
                {"href":"https://staging.dnsaas.rackspace.net/v1.0/5800438/"
                        "domains/2787310/records?limit=1&offset=578",
                 "rel":"next"
                }]
            }))
        self.mox.ReplayAll()

        records = RecordsManager(dns)
        list, offset = records.page_list("fake.com")
        self.assertEqual(2, len(list))
        self.assertTrue('a' in list)
        self.assertTrue('b' in list)
        self.assertEqual(578, offset)

    def test_page_list_when_no_offsets_returned(self):
        """Makes sure we throw if multiple offsets are found."""
        client = self.mox.CreateMock(DNSaasClient)
        dns = FakeDNSaaS(client, None, None)
        dns.client.get("fake.com").AndReturn((None,
              {"records":[ 'a' ],
               "links":[
                       {"href":"https://blah.com?limit=1",
                        "rel":"next"
                   }]
          }))
        self.mox.ReplayAll()
        records = RecordsManager(dns)
        list, offset = records.page_list("fake.com")
        self.assertTrue(offset is None)
        self.assertEqual(1, len(list))
        self.assertEqual('a', list[0])

    def test_page_list_when_multiple_offsets_returned(self):
        """Makes sure we throw if multiple offsets are found."""
        client = self.mox.CreateMock(DNSaasClient)
        dns = FakeDNSaaS(client, None, None)
        dns.client.get("fake.com").AndReturn((None,
              {"records":[ 'a', 'b' ],
               "links":[
                       {"href":"https://blah.com?limit=1&offset=578&offset=1",
                        "rel":"next"
                   }]
          }))
        self.mox.ReplayAll()
        records = RecordsManager(dns)
        self.assertRaises(RuntimeError, records.page_list, "fake.com")

