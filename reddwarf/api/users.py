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

import webob

from nova import compute
from nova import log as logging
from nova.api.openstack import wsgi

from reddwarf import exception
from reddwarf.api import common
from reddwarf.api import deserializer
from reddwarf.db import api as dbapi
from reddwarf.guest import api as guest_api
from reddwarf.guest.db import models


LOG = logging.getLogger('reddwarf.api.users')
LOG.setLevel(logging.DEBUG)


class Controller(object):
    """ The User Controller for the Platform API """

    def __init__(self):
        self.guest_api = guest_api.API()
        self.compute_api = compute.API()
        super(Controller, self).__init__()

    def show(self, req, instance_id, id):
        raise exception.NotImplemented()
    
    def index(self, req, instance_id):
        """ Returns a list database users for the db instance """
        LOG.info("Call to Users index - %s", instance_id)
        LOG.debug("%s - %s", req.environ, req.body)
        local_id = dbapi.localid_from_uuid(instance_id)
        ctxt = req.environ['nova.context']
        common.instance_available(ctxt, instance_id, local_id, self.compute_api)
        try:
            result = self.guest_api.list_users(ctxt, local_id)
        except Exception as err:
            LOG.error(err)
            raise exception.InstanceFault("Unable to get the list of users")
        LOG.debug("LIST USERS RESULT - %s", str(result))
        users = {'users':[]}
        for user in result:
            mysql_user = models.MySQLUser()
            mysql_user.deserialize(user)
            dbs = []
            for db in mysql_user.databases:
                dbs.append({'name': db['_name']})
            users['users'].append({'name': mysql_user.name, 'databases': dbs})
        LOG.debug("LIST USERS RETURN - %s", users)
        return users

    def delete(self, req, instance_id, id):
        """ Deletes a user in the db instance """
        LOG.info("Call to Delete User - %s for instance %s",
                 id, instance_id)
        LOG.debug("%s - %s", req.environ, req.body)
        local_id = dbapi.localid_from_uuid(instance_id)
        ctxt = req.environ['nova.context']
        common.instance_available(ctxt, instance_id, local_id, self.compute_api)
        try:
            user = models.MySQLUser()
            user.name = id
        except ValueError as ve:
            LOG.error(ve)
            raise exception.BadRequest(ve.message)

        self.guest_api.delete_user(ctxt, local_id, user.serialize())
        return webob.Response(status_int=202)

    def create(self, req, instance_id, body):
        """ Creates a new user for the db instance """
        self._validate(body)

        LOG.info("Call to Create Users for instance %s", instance_id)
        LOG.debug("%s - %s", req.environ, body)
        local_id = dbapi.localid_from_uuid(instance_id)
        ctxt = req.environ['nova.context']
        common.instance_available(ctxt, instance_id, local_id, self.compute_api)

        users = common.populate_users(body.get('users', ''))
        self.guest_api.create_user(ctxt, local_id, users)
        return webob.Response(status_int=202)

    def _validate(self, body):
        """Validate that the request has all the required parameters"""
        if not body:
            raise exception.BadRequest("The request contains an empty body")

        if not body.get('users', ''):
            raise exception.BadRequest("Required element/key 'users' was not "
                                       "specified")
        for user in body.get('users'):
            if not user.get('name'):
                raise exception.BadRequest("Required attribute/key 'name' was "
                                           "not specified")
            if not user.get('password'):
                raise exception.BadRequest("Required attribute/key 'password' "
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
