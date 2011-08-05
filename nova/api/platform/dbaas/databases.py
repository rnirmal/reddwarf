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
from nova.api.platform.dbaas import common
from nova.api.platform.dbaas import deserializer
from nova.guest import api as guest_api
from nova.guest.db import models


LOG = logging.getLogger('nova.api.platform.dbaas.databases')
LOG.setLevel(logging.DEBUG)


class Controller(object):
    """ The Database Controller for the DBaaS API """

    def __init__(self):
        self.guest_api = guest_api.API()
        self.compute_api = compute.API()
        super(Controller, self).__init__()

    def show(self, req, dbcontainer_id, id):
        raise exc.HTTPNotImplemented()

    def index(self, req, dbcontainer_id):
        """ Returns a list of Databases for the DBContainer """
        LOG.info("Call to Databases index - %s", dbcontainer_id)
        LOG.debug("%s - %s", req.environ, req.body)
        ctxt = req.environ['nova.context']
        common.instance_exists(ctxt, dbcontainer_id, self.compute_api)
        result = self.guest_api.list_databases(ctxt, dbcontainer_id)
        LOG.debug("LIST DATABASES RESULT - %s", str(result))
        databases = {'databases':[]}
        for database in result:
            mysql_database = models.MySQLDatabase()
            mysql_database.deserialize(database)
            databases['databases'].append({'name': mysql_database.name})
        LOG.debug("LIST DATABASES RETURN - %s", databases)
        return databases

    def delete(self, req, dbcontainer_id, id):
        """ Deletes a Database """
        LOG.info("Call to Delete Database - %s for container %s",
                 id, dbcontainer_id)
        LOG.debug("%s - %s", req.environ, req.body)
        ctxt = req.environ['nova.context']
        common.instance_exists(ctxt, dbcontainer_id, self.compute_api)
        mydb = models.MySQLDatabase()
        mydb.name = id

        self.guest_api.delete_database(ctxt, dbcontainer_id, mydb.serialize())
        return exc.HTTPAccepted()

    def create(self, req, dbcontainer_id, body):
        """ Creates a new Database in the specified container """
        self._validate(body)

        LOG.info("Call to Create Databases for container %s", dbcontainer_id)
        LOG.debug("%s - %s", req.environ, body)
        ctxt = req.environ['nova.context']
        common.instance_exists(ctxt, dbcontainer_id, self.compute_api)

        databases = common.populate_databases(body.get('databases', ''))
        self.guest_api.create_database(ctxt, dbcontainer_id, databases)
        return exc.HTTPAccepted("")

    def _validate(self, body):
        """Validate that the request has all the required parameters"""
        if not body:
            raise exc.HTTPUnprocessableEntity()

        if not body.get('databases', ''):
            raise exception.ApiError("Required element/key 'databases' " \
                                      "was not specified")
        for database in body.get('databases'):
            if not database.get('name', ''):
                raise exception.ApiError("Required attribute/key 'name' " \
                                         "was not specified")


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
