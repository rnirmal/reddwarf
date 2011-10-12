# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2010 OpenStack LLC.
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

from webob import exc

from nova import compute
from nova import exception
from nova import log as logging
from nova.api.openstack import faults
from nova.api.openstack import wsgi
from reddwarf.api import common
from reddwarf.api import deserializer
from nova.guest import api as guest_api
from nova.guest.db import models


LOG = logging.getLogger('reddwarf.api.users')
LOG.setLevel(logging.DEBUG)


class Controller(object):
    """ The User Controller for the Platform API """

    def __init__(self):
        self.guest_api = guest_api.API()
        self.compute_api = compute.API()
        super(Controller, self).__init__()

    def show(self, req, instance_id, id):
        return faults.Fault(exc.HTTPNotImplemented())
    
    def index(self, req, instance_id):
        """ Returns a list database users for the db instance """
        LOG.info("Call to Users index - %s", instance_id)
        LOG.debug("%s - %s", req.environ, req.body)
        ctxt = req.environ['nova.context']
        common.instance_exists(ctxt, instance_id, self.compute_api)
        result = self.guest_api.list_users(ctxt, instance_id)
        LOG.debug("LIST USERS RESULT - %s", str(result))
        users = {'users':[]}
        for user in result:
            mysql_user = models.MySQLUser()
            mysql_user.deserialize(user)
            users['users'].append({'name': mysql_user.name})
        LOG.debug("LIST USERS RETURN - %s", users)
        return users

    def delete(self, req, instance_id, id):
        """ Deletes a user in the db instance """
        LOG.info("Call to Delete User - %s for instance %s",
                 id, instance_id)
        LOG.debug("%s - %s", req.environ, req.body)
        ctxt = req.environ['nova.context']
        common.instance_exists(ctxt, instance_id, self.compute_api)
        user = models.MySQLUser()
        user.name = id

        self.guest_api.delete_user(ctxt, instance_id, user.serialize())
        return exc.HTTPAccepted()

    def create(self, req, instance_id, body):
        """ Creates a new user for the db instance """
        self._validate(body)

        LOG.info("Call to Create Users for instance %s", instance_id)
        LOG.debug("%s - %s", req.environ, body)
        ctxt = req.environ['nova.context']
        common.instance_exists(ctxt, instance_id, self.compute_api)

        users = common.populate_users(body.get('users', ''))
        self.guest_api.create_user(ctxt, instance_id, users)
        return exc.HTTPAccepted()

    def _validate(self, body):
        """Validate that the request has all the required parameters"""
        if not body:
            return faults.Fault(exc.HTTPUnprocessableEntity())

        if not body.get('users', ''):
            raise exception.ApiError("Required element/key 'users' " \
                                         "was not specified")
        for user in body.get('users'):
            if not user.get('name'):
                raise exception.ApiError("Required attribute/key 'name' " \
                                         "was not specified")
            if not user.get('password'):
                raise exception.ApiError("Required attribute/key 'password' " \
                                         "was not specified")


def create_resource(version='1.0'):
    controller = {
        '1.0': Controller,
    }[version]()

    metadata = {
        "attributes": {
            'user': ['name', 'password']
        },
    }

    xmlns = {
        '1.0': common.XML_NS_V10,
    }[version]

    serializers = {
        'application/xml': wsgi.XMLDictSerializer(metadata=metadata,
                                                  xmlns=xmlns),
    }

    deserializers = {
        'application/xml': deserializer.UserXMLDeserializer(),
    }

    response_serializer = wsgi.ResponseSerializer(body_serializers=serializers)
    request_deserializer = wsgi.RequestDeserializer(body_deserializers=deserializers)

    return wsgi.Resource(controller, deserializer=request_deserializer,
                         serializer=response_serializer)
