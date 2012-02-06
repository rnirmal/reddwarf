import unittest
import httplib2
import mox
import json

from eventlet import pools

from novaclient import client
from novaclient import exceptions
from rsdns.client import DNSaas


fake_response = httplib2.Response({"status": 200})
fake_body = '{"hi": "there", "auth": {"token": {"id": "token_id_value"}}}'

def get_client(fake_request_method):
    cl = DNSaas("1234", "username", "password",
                auth_url="auth_url",
                management_base_url="mgmt_url")
    class FakeHttpLib2(object):
        pass

    FakeHttpLib2.request = fake_request_method
    cl.client.http_pool = pools.Pool()
    cl.client.http_pool.create = FakeHttpLib2
    return cl

def mock_request(self, *args, **kwargs):
    return fake_response, fake_body

def mock_request_bad(self, *args, **kwargs):
    return httplib2.Response({"status": 401}), \
           '{"message": "Invalid authentication token. Please renew."}'


class DNSClientAuthFailPassTest(unittest.TestCase):

    def setUp(self):
        self.old_request =httplib2.Http.request
        self.mox = mox.Mox()

    def tearDown(self):
        httplib2.Http.request = self.old_request
        self.mox.VerifyAll()

    def test_auth_fail(self):
        my_client = get_client(mock_request_bad)

        def test_auth_call():
            self.assertRaises(exceptions.HTTPNotImplemented, my_client.authenticate)

        self.mox.ReplayAll()
        test_auth_call()

    def test_auth_pass(self):
        my_client = get_client(mock_request)

        def test_get_call():
            resp, body = my_client.client.request("/list")
            self.assertEqual(resp['status'], 200)
            self.assertEqual(json.dumps(body), fake_body)

        self.mox.ReplayAll()
        test_get_call()

    def test_auth_fail_then_retry(self):
        # This is the ultimate test of the dns retry.
        #
        # To see that this test is working you can force a failure by
        # asserting status is 202 or something and it will show the logs
        # of failing the first time and successfully the second time
        # calling the http.request method.

        self.count = 0
        def fake_request(_self, *args, **kwargs):
            self.count += 1
            if self.count > 1:
                return mock_request(_self, *args, **kwargs)
            else:
                return mock_request_bad(_self, *args, **kwargs)

        my_client = get_client(fake_request)

        def test_auth_call():
            resp, body = my_client.client.request("/list")
            self.assertEqual(resp['status'], 200)
            self.assertEqual(json.dumps(body), fake_body)
            self.assertEqual(my_client.client.auth_token, "token_id_value")

        self.mox.ReplayAll()
        test_auth_call()
