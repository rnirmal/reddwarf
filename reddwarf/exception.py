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

from webob import exc


class BadRequest(exc.WSGIHTTPException, Exception):
    def __init__(self, message="The server could not comply with the request "
                       "since it is either malformed or otherwise incorrect."):
        self.explanation = message
        self.code = 400
        errstr = '%s: %s' % (self.code, self.explanation)
        super(BadRequest, self).__init__(errstr)


class Unauthorized(exc.WSGIHTTPException, Exception):
    def __init__(self, message="The server could not verify that you are "
                               "authorized to access the requested resource"):
        self.explanation = message
        self.code = 401
        errstr = '%s: %s' % (self.code, self.explanation)
        super(Unauthorized, self).__init__(errstr)


class NotFound(exc.WSGIHTTPException, Exception):
    def __init__(self, message="The resource could not be found"):
        self.explanation = message
        self.code = 404
        errstr = '%s: %s' % (self.code, self.explanation)
        super(NotFound, self).__init__(errstr)


class UnprocessableEntity(exc.WSGIHTTPException, Exception):
    def __init__(self, message="Unable to process the contained request"):
        self.explanation = message
        self.code = 422
        errstr = '%s: %s' % (self.code, self.explanation)
        super(UnprocessableEntity, self).__init__(errstr)


class InstanceFault(exc.WSGIHTTPException, Exception):
    def __init__(self, message="The server has either erred or is incapable "
                               "of performing the requested operation."):
        self.explanation = message
        self.code = 500
        errstr = '%s: %s' % (self.code, self.explanation)
        super(InstanceFault, self).__init__(errstr)


class NotImplemented(exc.WSGIHTTPException, Exception):
    def __init__(self, message="The requested method is not implemented"):
        self.explanation = message
        self.code = 501
        errstr = '%s: %s' % (self.code, self.explanation)
        super(NotImplemented, self).__init__(errstr)


class ServiceUnavailable(exc.WSGIHTTPException, Exception):
    def __init__(self, message="The service is not available at this time"):
        self.explanation = message
        self.code = 503
        errstr = '%s: %s' % (self.code, self.explanation)
        super(ServiceUnavailable, self).__init__(errstr)
