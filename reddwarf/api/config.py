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

from nova import log as logging
from nova.api.openstack import wsgi

from reddwarf import exception
from reddwarf.api import common
from reddwarf.api import deserializer
from reddwarf.db import api as dbapi


LOG = logging.getLogger('reddwarf.api.config')
LOG.setLevel(logging.DEBUG)


class Controller(object):
    """ The Config Controller for the Reddwarf Management API"""

    def __init__(self):
        super(Controller, self).__init__()

    @common.verify_admin_context
    def show(self, req, id):
        LOG.info("List config entry %s" % id)
        LOG.debug("%s - %s", req.environ, req.body)
        try:
            config = dbapi.config_get(id)
        except exception.ConfigNotFound as cnf:
            raise exception.NotFound(cnf._error_string)
        return {'config': {'key': config.key, 'value': config.value,
                            'description': config.description}}

    @common.verify_admin_context
    def index(self, req):
        """ Returns a list of all config values"""
        LOG.info("List all config entries")
        LOG.debug("%s - %s", req.environ, req.body)
        try:
            configs_data = dbapi.config_get_all()
        except exception.ConfigNotFound as cnf:
            raise exception.NotFound(cnf._error_string)
        configs = []
        for config in configs_data:
            entry = {'key': config.key, 'value': config.value,
                     'description': config.description}
            configs.append(entry)
        return {'configs': configs}

    @common.verify_admin_context
    def delete(self, req, id):
        """ Deletes a config entry"""
        LOG.info("Delete config entry %s" % id)
        LOG.debug("%s - %s", req.environ, req.body)
        dbapi.config_delete(id)
        return exc.HTTPOk()

    @common.verify_admin_context
    def create(self, req, body):
        """ Creates a new config entry"""
        LOG.info("Create a new config entry")
        LOG.debug("%s - %s", req.environ, req.body)
        self._validate_create(body)
        try:
            for config in body['configs']:
                dbapi.config_create(config.get('key'),
                                    config.get('value', None),
                                    config.get('description', None))
        except exception.DuplicateConfigEntry as dce:
            raise exception.InstanceFault(dce._error_string)
        return exc.HTTPOk()

    @common.verify_admin_context
    def update(self, req, id, body):
        """Update an existing config entry"""
        LOG.info("Update config entry %s" % id)
        LOG.debug("%s - %s", req.environ, req.body)
        self._validate_update(body)
        config = body['config']
        dbapi.config_update(config.get('key'), config.get('value', None),
                            config.get('description', None))
        return exc.HTTPOk()

    def _validate(self, body):
        """Validate that the request has all the required parameters"""
        if not body:
            raise exception.BadRequest("The request contains an empty body")

    def _validate_create(self, body):
        self._validate(body)
        if not body.get('configs', ''):
            raise exception.BadRequest("Required element/key 'configs' was "
                                       "not specified")
        for config in body.get('configs'):
            if not config.get('key'):
                raise exception.BadRequest("Required attribute/key 'key' was "
                                           "not specified")

    def _validate_update(self, body):
        self._validate(body)
        config = body.get('config', '')
        if not config:
            raise exception.BadRequest("Required element/key 'config' was not "
                                       "specified")
        if not config.get('key'):
                raise exception.BadRequest("Required attribute/key 'key' was "
                                           "not specified")


def create_resource(version='1.0'):
    controller = {
        '1.0': Controller,
    }[version]()

    metadata = {
        "attributes": {
            'config': ['key', 'value', 'description']
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
        'application/xml': deserializer.ConfigXMLDeserializer(),
    }

    response_serializer = wsgi.ResponseSerializer(body_serializers=serializers)
    request_deserializer = wsgi.RequestDeserializer(body_deserializers=deserializers)

    return wsgi.Resource(controller, deserializer=request_deserializer,
                         serializer=response_serializer)
