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
from nova import log as logging
from nova.api.openstack import wsgi

from reddwarf import exception
from reddwarf.api import common
from reddwarf.api import deserializer
from reddwarf.db import api as dbapi
from reddwarf.guest import api as guest_api
from reddwarf.guest.db import models

LOG = logging.getLogger('reddwarf.api.databases')
LOG.setLevel(logging.DEBUG)


class Controller(object):
    """ The Database Controller for the DBaaS API """

    def __init__(self):
        self.guest_api = guest_api.API()
        self.compute_api = compute.API()
        super(Controller, self).__init__()

    def show(self, req, instance_id, id):
        raise exception.NotImplemented()

    def index(self, req, instance_id):
        """ Returns a list of Databases for the Instance """
        LOG.info("Call to Databases index - %s", instance_id)
        LOG.debug("%s - %s", req.environ, req.body)
        local_id = dbapi.localid_from_uuid(instance_id)
        ctxt = req.environ['nova.context']
        common.instance_available(ctxt, instance_id, local_id, self.compute_api)
        try:
            result = self.guest_api.list_databases(ctxt, local_id)
        except Exception as err:
            LOG.error(err)
            raise exception.InstanceFault("Unable to get the list of databases")
        LOG.debug("LIST DATABASES RESULT - %s", str(result))
        databases = {'databases':[]}
        for database in result:
            mysql_database = models.MySQLDatabase()
            mysql_database.deserialize(database)
            databases['databases'].append({'name': mysql_database.name})
        LOG.debug("LIST DATABASES RETURN - %s", databases)
        return databases

    def delete(self, req, instance_id, id):
        """ Deletes a Database """
        LOG.info("Call to Delete Database - %s for instance %s",
                 id, instance_id)
        LOG.debug("%s - %s", req.environ, req.body)
        local_id = dbapi.localid_from_uuid(instance_id)
        ctxt = req.environ['nova.context']
        common.instance_available(ctxt, instance_id, local_id, self.compute_api)
        try:
            mydb = models.MySQLDatabase()
            mydb.name = id
        except ValueError as ve:
            LOG.error(ve)
            raise exception.BadRequest(ve.message)

        self.guest_api.delete_database(ctxt, local_id, mydb.serialize())
        return exc.HTTPAccepted()

    def create(self, req, instance_id, body):
        """ Creates a new Database in the specified instance """
        self._validate(body)

        LOG.info("Call to Create Databases for instance %s", instance_id)
        LOG.debug("%s - %s", req.environ, body)
        local_id = dbapi.localid_from_uuid(instance_id)
        ctxt = req.environ['nova.context']
        common.instance_available(ctxt, instance_id, local_id, self.compute_api)

        databases = common.populate_databases(body.get('databases', ''))
        self.guest_api.create_database(ctxt, local_id, databases)
        return exc.HTTPAccepted("")

    def _validate(self, body):
        """Validate that the request has all the required parameters"""
        if not body:
            raise exception.BadRequest("The request contains an empty body")

        if not body.get('databases', ''):
            raise exception.BadRequest("Required element/key 'databases' was "
                                       "not specified")
        for database in body.get('databases'):
            if not database.get('name', ''):
                raise exception.BadRequest("Required attribute/key 'name' was "
                                           "not specified")


def create_resource(version='1.0'):
    controller = {
        '1.0': Controller,
    }[version]()

    metadata = {
        "attributes": {
            'database': ["name", "character_set", "collate"]
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
        'application/xml': deserializer.DatabaseXMLDeserializer(),
    }

    response_serializer = wsgi.ResponseSerializer(body_serializers=serializers)
    request_deserializer = wsgi.RequestDeserializer(body_deserializers=deserializers)

    return wsgi.Resource(controller, deserializer=request_deserializer,
                         serializer=response_serializer)
