import httplib2
import mox
import unittest

from eventlet import pools

from novaclient.client import HTTPClient
from novaclient import exceptions
from rsdns.client.dns_client import DNSaasClient

ACCOUNT_ID = 1155
USERNAME = "test_user"
API_KEY="key"
AUTH_URL="urly"
MANAGEMENT_BASE_URL="mgmter"


class FakeResponse(object):

    def __init__(self, status):
        self.status = status

class WhenDNSaasClientConnectsSuccessfully(unittest.TestCase):

    def setUp(self):
        self.mox = mox.Mox()

    def tearDown(self):
        self.mox.VerifyAll()

    def fake_auth(self, *args, **kwargs):
        self.auth_called = True


    def create_mock_client(self, fake_request_method):
        """
        Creates a mocked DNSaasClient object, which calls "fake_request_method"
        instead of httplib2.request.
        """
        class FakeHttpLib2(object):
            pass

        FakeHttpLib2.request = fake_request_method
        mock_client = self.mox.CreateMock(DNSaasClient)
        mock_client.http_pool = pools.Pool()
        mock_client.http_pool.create = FakeHttpLib2
        mock_client.auth_token = 'token'
        return mock_client


    def test_make_request(self):
        kwargs = {
            'headers': {},
            'body': "{}"
        }
        def fake_request(self, *args, **kwargs):
            return FakeResponse(200), '{"hi":"hello"}'

        mock_client = self.create_mock_client(fake_request)
        resp, body = DNSaasClient.request(mock_client, **kwargs)
        self.assertEqual(200, resp.status)
        self.assertEqual({"hi":"hello"}, body)

    def test_make_request_with_old_token(self):
        kwargs = {
            'headers': {},
            'body': '{"message":"Invalid authentication token. Please renew."}'
        }
        def fake_request(self, *args, **kwargs):
            return FakeResponse(401), \
                '{"message":"Invalid authentication token. Please renew."}'

        mock_client = self.create_mock_client(fake_request)
        mock_client.authenticate()
        mock_client.authenticate()
        mock_client.authenticate()
        self.mox.ReplayAll()
        self.assertRaises(exceptions.Unauthorized, DNSaasClient.request,
                          mock_client, **kwargs)

    def test_make_request_with_old_token_2(self):
        kwargs = {
            'headers': {},
            'body': "{}"
        }
        self.count = 0
        def fake_request(_self, *args, **kwargs):
            self.count += 1
            if self.count > 1:
                return FakeResponse(200), '{"hi":"hello"}'
            else:
                return FakeResponse(401), \
                    '{"message":"Invalid authentication token. ' \
                    'Please renew."}'

        mock_client = self.create_mock_client(fake_request)
        mock_client.authenticate()
        self.mox.ReplayAll()
        resp, body = DNSaasClient.request(mock_client, **kwargs)
        self.assertEqual(200, resp.status)
        self.assertEqual({"hi":"hello"}, body)



