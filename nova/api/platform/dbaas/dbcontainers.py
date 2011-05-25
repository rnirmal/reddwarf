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
from nova import flags
from nova import log as logging
from nova import utils
from nova.api.openstack import servers
from nova.api.platform.dbaas import common
from nova.api.platform.dbaas import deserializer
from nova.compute import power_state
from nova.exception import InstanceNotFound
from nova.guest import api as guest_api
from reddwarf.db import api as dbapi


LOG = logging.getLogger('nova.api.platform.dbaas.dbcontainers')
LOG.setLevel(logging.DEBUG)


FLAGS = flags.FLAGS
flags.DEFINE_string('reddwarf_imageRef', 'http://localhost:8775/v1.0/images/1',
                    'Default image for reddwarf')

_dbaas_mapping = {
    None: 'BUILD',
    power_state.NOSTATE: 'BUILD',
    power_state.RUNNING: 'ACTIVE',
    power_state.SHUTDOWN: 'SHUTDOWN',
    power_state.BUILDING: 'BUILD',
}


class Controller(common.DBaaSController):
    """ The DBContainer API controller for the Platform API """

    _serialization_metadata = {
        'application/xml': {
            "attributes": {
                "dbcontainer": ["id", "name", "status", "flavorRef"],
                "dbtype": ["name", "version"],
                "link": ["rel", "type", "href"],
            },
        },
    }

    def __init__(self):
        self.compute_api = compute.API()
        self.guest_api = guest_api.API()
        self.server_controller = servers.ControllerV11()
        super(Controller, self).__init__()

    def index(self, req):
        """ Returns a list of dbcontainer names and ids for a given user """
        LOG.info("Call to DBContainers index test")
        LOG.debug("%s - %s", req.environ, req.body)
        resp = {'dbcontainers': self.server_controller.index(req)['servers']}
        for t in resp['dbcontainers']:
            self._remove_excess_fields(t)
            # TODO(cp16net)
            # make a guest status get function that allows you
            # to pass a list of container ids
            try:
                result = dbapi.guest_status_get(t['id'])
                state = result.state
                t['status'] = _dbaas_mapping[state]
            except InstanceNotFound:
                # should we set the state to build/shutdown here?
                pass
        return resp

    def detail(self, req):
        """ Returns a list of dbcontainer details for a given user """
        LOG.info("Call to DBContainers detail")
        LOG.debug("%s - %s", req.environ, req.body)
        resp = {'dbcontainers': self.server_controller.detail(req)['servers']}
        for t in resp['dbcontainers']:
            self._remove_excess_fields(t)
            # TODO(cp16net)
            # make a guest status get function that allows you
            # to pass a list of container ids
            try:
                # if i delete a container and then list details right after i kept getting
                # a instance not found exception when trying to get the guest status.
                result = dbapi.guest_status_get(t['id'])
                state = result.state
                t['status'] = _dbaas_mapping[state]
            except InstanceNotFound:
                # should we set the state to build/shutdown here?
                pass
        return resp

    def show(self, req, id):
        """ Returns dbcontainer details by container id """
        LOG.info("Get Container by ID - %s", id)
        LOG.debug("%s - %s", req.environ, req.body)
        response = self.server_controller.show(req, id)
        if isinstance(response, Exception):
            return response  # Just return the exception to throw it
        resp = {'dbcontainer': response['server']}
        self._remove_excess_fields(resp['dbcontainer'])
        try:
            result = dbapi.guest_status_get(instance_id=id)
            state = result.state
            resp['dbcontainer']['status'] = _dbaas_mapping[state]
        except InstanceNotFound:
            pass
        return resp

    def delete(self, req, id):
        """ Destroys a dbcontainer """
        LOG.info("Delete Container by ID - %s", id)
        LOG.debug("%s - %s", req.environ, req.body)
        result = self.server_controller.delete(req, id)
        if isinstance(result, exc.HTTPAccepted):
            dbapi.guest_status_delete(id)
        return result

    def create(self, req):
        """ Creates a new DBContainer for a given user """
        LOG.info("Create Container")
        LOG.debug("%s - %s", req.environ, req.body)
        env, body = self._deserialize_create(req)
        req.body = str(body)

        databases = common.populate_databases(
                                    env['dbcontainer'].get('databases', ''))

        server = self.server_controller.create(req)

        server_id = str(server['server']['id'])
        # Send the prepare call to Guest
        ctxt = req.environ['nova.context']
        dbapi.guest_status_create(server_id)
        self.guest_api.prepare(ctxt, server_id, databases)
        resp = {'dbcontainer': server['server']}
        self._remove_excess_fields(resp['dbcontainer'])
        return resp

    def _remove_excess_fields(self, response):
        """ Removes the excess fields from the parent dbcontainer call.

        We delete elements but if the call came from the index function
        the response will not have all the fields and we expect some to
        raise a key error exception.
        """
        LOG.debug("Removing the excess information from the containers.")
        for attr in ["hostId","imageRef","metadata","adminPass"]:
            if response.has_key(attr):
                del response[attr]
        return response

    def _deserialize_create(self, request):
        """ Deserialize a create request

        Overrides normal behavior in the case of xml content
        """
        if request.content_type == "application/xml":
            deser = deserializer.RequestXMLDeserializer()
            return deser.deserialize_create(request.body)
        else:
            deser = deserializer.RequestJSONDeserializer()
            env = self._deserialize(request.body, request.get_content_type())
            return env, deser.deserialize_create(request.body)
