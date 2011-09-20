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

"""
DNS Client interface. Child of OpenStack client to handle auth issues.
We have to duplicate a lot of code from the OpenStack client since so much
is different here.
"""

from novaclient.client import HTTPClient
from novaclient import exceptions
import httplib2

from nova import log as logging

try:
    import json
except ImportError:
    import simplejson as json

LOG = logging.getLogger('rsdns.client.dns_client')


class DNSaasClient(HTTPClient):

    def __init__(self, accountId, user, apikey, auth_url, management_base_url):
        tenant = "dbaas"    
        super(DNSaasClient, self).__init__(user, apikey, tenant, auth_url)
        self.accountId = accountId
        self.management_base_url = management_base_url

    def authenticate(self):
        #headers = {'X-Auth-User': self.user, 'X-Auth-Key': self.apikey}
#        LOG.debug("Performing GET on %s, with headers=%s" % (self.auth_url,
        #resp, body = self.request(self.auth_url + "", 'GET', headers=headers)
#                                                      headers))
        http = httplib2.Http()
        headers = {'Content-Type': 'application/json'}
        body = {'credentials':{'username':self.user, 'key':self.apikey}}
        resp, resp_body = http.request(self.auth_url, "POST", headers=headers,
                                       body=json.dumps(body))
        resp_body = json.loads(resp_body)
        LOG.debug(json.dumps({'body':resp_body, 'resp':resp}, sort_keys=True,
                             indent=4))
        self.auth_token = resp_body['auth']['token']['id']

        self.management_url = self.management_base_url + str(self.accountId)
        #self.auth_token = resp['x-auth-token']

        LOG.debug("AUTH_TOKEN=%s" % self.auth_token)

    def _munge_get_url(self, url):
        return url  # Don't munge this.

    def request(self, *args, **kwargs):
       kwargs.setdefault('headers', {})
       kwargs['headers']['User-Agent'] = self.USER_AGENT
       if 'body' in kwargs:
           kwargs['headers']['Content-Type'] = 'application/json'
           kwargs['body'] = json.dumps(kwargs['body'])

       LOG.debug("ARGS:" + str(args))
       LOG.debug("HEADERS:" + str(kwargs['headers']))
       resp, body = httplib2.Http.request(self, *args, **kwargs)
       body = json.loads(body)
       LOG.debug("RESPONSE:" + str(resp))
       LOG.debug("BODY:" + str(body))

       if resp.status in (400, 401, 403, 404, 413, 500, 501):
           raise exception_from_response(resp, body)

       return resp, body




def exception_from_response(response, body):
    """
    Return an instance of an OpenStackException or subclass
    based on an httplib2 response.

    Usage::

        resp, body = http.request(...)
        if resp.status != 200:
            raise exception_from_response(resp, body)
    """
    cls = exceptions._code_map.get(response.status, exceptions.ClientException)
    if body:
        message = "n/a"
        details = "n/a"
        if hasattr(body, 'keys'):
            error = body[body.keys()[0]]
            try:
                message = error.get('message', None)
                details = error.get('details', None)
            except AttributeError:
                message = error
                details = error
        return cls(code=response.status, message=message, details=details)
    else:
        return cls(code=response.status)
