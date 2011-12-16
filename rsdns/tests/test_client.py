import httplib2
import mox
import unittest

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
        self.old_request =httplib2.Http.request
        self.mox = mox.Mox()

    def tearDown(self):
        httplib2.Http.request = self.old_request
        self.mox.VerifyAll()

    def fake_auth(self, *args, **kwargs):
        self.auth_called = True

    def test_make_request(self):
        kwargs = {
            'headers': {},
            'body': "{}"
        }
        def fake_request(self, *args, **kwargs):
            return FakeResponse(200), '{"hi":"hello"}'
        httplib2.Http.request = fake_request
        mock_client = self.mox.CreateMock(DNSaasClient)
        mock_client.auth_token = 'token'
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
        httplib2.Http.request = fake_request
        mock_client = self.mox.CreateMock(DNSaasClient)
        mock_client.auth_token = 'token'
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
                   '{"message":"Invalid authentication token. Please renew."}'
        httplib2.Http.request = fake_request
        mock_client = self.mox.CreateMock(DNSaasClient)
        mock_client.auth_token = 'token'
        mock_client.authenticate()
        self.mox.ReplayAll()
        resp, body = DNSaasClient.request(mock_client, **kwargs)
        self.assertEqual(200, resp.status)
        self.assertEqual({"hi":"hello"}, body)



