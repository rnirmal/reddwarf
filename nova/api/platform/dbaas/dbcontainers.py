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
from nova import db
from nova import exception
from nova import flags
from nova import log as logging
from nova import volume
from nova import utils
from nova.api.openstack import faults
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
flags.DEFINE_string('reddwarf_mysql_data_dir', 'reddwarf_mysql_data_dir',
                    'Mount point within the container for MySQL data.')

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
                "dbcontainer": ["id", "name", "status", "flavorRef", "rootEnabled"],
                "dbtype": ["name", "version"],
                "link": ["rel", "type", "href"],
            },
        },
    }

    def __init__(self):
        self.compute_api = compute.API()
        self.dns_entry_factory = \
            utils.import_object(FLAGS.dns_instance_entry_factory)
        self.guest_api = guest_api.API()
        self.server_controller = servers.ControllerV11()
        self.volume_api = volume.API()
        super(Controller, self).__init__()

    def index(self, req):
        """ Returns a list of dbcontainer names and ids for a given user """
        LOG.info("Call to DBContainers index test")
        LOG.debug("%s - %s", req.environ, req.body)
        resp = {'dbcontainers': self.server_controller.index(req)['servers']}
        for container in resp['dbcontainers']:
            self._modify_fields(req, container)
            # TODO(cp16net)
            # make a guest status get function that allows you
            # to pass a list of container ids
            try:
                result = dbapi.guest_status_get(container['id'])
                container['status'] = _dbaas_mapping[result.state]
            except InstanceNotFound:
                # we set the state to shutdown if not found
                container['status'] = _dbaas_mapping[power_state.SHUTDOWN]
        return resp

    def detail(self, req):
        """ Returns a list of dbcontainer details for a given user """
        LOG.info("Call to DBContainers detail")
        LOG.debug("%s - %s", req.environ, req.body)
        resp = {'dbcontainers': self.server_controller.detail(req)['servers']}
        for container in resp['dbcontainers']:
            self._modify_fields(req, container)
            # TODO(cp16net)
            # make a guest status get function that allows you
            # to pass a list of container ids
            try:
                result = dbapi.guest_status_get(container['id'])
                container['status'] = _dbaas_mapping[result.state]
            except InstanceNotFound:
                # we set the state to shutdown if not found
                container['status'] = _dbaas_mapping[power_state.SHUTDOWN]
            enabled = self._determine_root(req, container, container['id'])
            if enabled is not None:
                container['rootEnabled'] = enabled
        return resp

    def show(self, req, id):
        """ Returns dbcontainer details by container id """
        LOG.info("Get Container by ID - %s", id)
        LOG.debug("%s - %s", req.environ, req.body)
        response = self.server_controller.show(req, id)
        if isinstance(response, Exception):
            return response  # Just return the exception to throw it
        resp = {'dbcontainer': response['server']}
        self._modify_fields(req, resp['dbcontainer'])
        try:
            result = dbapi.guest_status_get(instance_id=id)
            resp['dbcontainer']['status'] = _dbaas_mapping[result.state]
        except InstanceNotFound:
            # we set the state to shutdown if not found
            resp['dbcontainer']['status']  = _dbaas_mapping[power_state.SHUTDOWN]
        enabled = self._determine_root(req, resp['dbcontainer'], id)
        if enabled is not None:
            resp['dbcontainer']['rootEnabled'] = enabled
        return resp

    def delete(self, req, id):
        """ Destroys a dbcontainer """
        LOG.info("Delete Container by ID - %s", id)
        LOG.debug("%s - %s", req.environ, req.body)
        result = self.server_controller.delete(req, id)
        if isinstance(result, exc.HTTPAccepted):
            dbapi.guest_status_delete(id)
        self.delete_volume(req, id)
        return result

    def create(self, req):
        """ Creates a new DBContainer for a given user """
        LOG.info("Create Container")
        LOG.debug("%s - %s", req.environ, req.body)
        env, body = self._deserialize_create(req)


        #TODO(tim.simpson) Check "env" to get volume options specified before
        #                  modifying the 'body' object with the volume_id.
        volume = self.create_volume(req)
        body.add_volume_id(volume['id'])
        body.add_mount_point(FLAGS.reddwarf_mysql_data_dir) # "/var/lib/mysql")

        req.body = body.serialize_for_create()

        self._setup_security_groups(req,
                                    FLAGS.default_firewall_rule_name,
                                    FLAGS.default_guest_mysql_port)

        databases = common.populate_databases(
                                    env['dbcontainer'].get('databases', ''))

        server = self._try_create_server(req)

        server_id = str(server['server']['id'])
        dbapi.guest_status_create(server_id)

        # Send the prepare call to Guest
        self.guest_api.prepare(req.environ['nova.context'],
                               server_id, databases)
        resp = {'dbcontainer': server['server']}
        self._modify_fields(req, resp['dbcontainer'])
        return resp

    def create_volume(self, req):
        """Creates the volume for the container and returns its ID."""
        #TODO(tim.simpson) Make volume create options configurable.
        context = req.environ['nova.context']
        return self.volume_api.create(context, size = 1,
                                      name="Volume",
                                      description="Stores database files.")

    def delete_volume(self, req, instance_id):
        """Delete the volume associated with this instance_id."""
        context = req.environ['nova.context']
        volumes = db.volume_get_all_by_instance(context, instance_id)
        for volume in volumes:
            self.volume_api.delete(context, volume['id'])

    def _try_create_server(self, req):
        """Handle the call to create a server through the openstack servers api.

        Separating this so we could do retries in the future and other processing of
        the result etc.
        """
        try:
            server = self.server_controller.create(req)
            if not server or isinstance(server, faults.Fault):
                if isinstance(server, faults.Fault):
                    LOG.error("%s: %s", server.wrapped_exc,
                              server.wrapped_exc.detail)
                raise exception.Error("Could not complete the request. " \
                                      "Please try again later or contact " \
                                      "Customer Support")
            return server
        except (TypeError, AttributeError, KeyError) as e:
            LOG.error(e)
            raise exception.Error(exc.HTTPUnprocessableEntity())

    def _modify_fields(self, req, response):
        """ Adds and removes the fields from the parent dbcontainer call.

        We delete elements but if the call came from the index function
        the response will not have all the fields and we expect some to
        raise a key error exception.

        """
        context = req.environ['nova.context']
        user_id=context.user_id
        instance_info = {"id": response["id"], "user_id": user_id}
        dns_entry = self.dns_entry_factory.create_entry(instance_info)
        if dns_entry:
            hostname = dns_entry.name
            response["hostname"] = hostname

        LOG.debug("Removing the excess information from the containers.")
        for attr in ["hostId","imageRef","metadata","adminPass"]:
            if response.has_key(attr):
                del response[attr]
        return response

    def _setup_security_groups(self, req, group_name, port):
        """ Setup a default firewall rule for reddwarf.

        We are using the existing infrastructure of security groups in nova
        used by the ec2 api and piggy back on it. Reddwarf by default will have
        one rule which will allow access to the specified tcp port, the default
        being 3306 from anywhere. For this the group_id and parent_id are the
        same, we are not doing any hierarchical rules yet.
        Here's how it would look in iptables.

        -A nova-compute-inst-<id> -p tcp -m tcp --dport 3306 -j ACCEPT
        """
        context = req.environ['nova.context']
        self.compute_api.ensure_default_security_group(context)

        if not db.security_group_exists(context, context.project_id, group_name):
            LOG.debug('Creating a new firewall rule %s for project %s'
                        % (group_name, context.project_id))
            values = {'name': group_name,
                      'description': group_name,
                      'user_id': context.user_id,
                      'project_id': context.project_id}
            security_group = db.security_group_create(context, values)
            rules = {'group_id': security_group['id'],
                     'parent_group_id': security_group['id'],
                     'cidr': '0.0.0.0/0',
                     'protocol': 'tcp',
                     'from_port': port,
                     'to_port': port}
            security_group_rule = db.security_group_rule_create(context, rules)
            self.compute_api.trigger_security_group_rules_refresh(context,
                                                          security_group['id'])

    def _deserialize_create(self, request):
        """ Deserialize a create request

        Overrides normal behavior in the case of xml content

        :retval A dictionary object representing the original request, followed
                by a SerializableMutableRequest representing 
                string representing the request deserialized with values changed.
        """
        if request.content_type == "application/xml":
            deser = deserializer.RequestXMLDeserializer()
            env, body = deser.deserialize_create(request.body)
        else:
            deser = deserializer.RequestJSONDeserializer()
            env = self._deserialize(request.body, request.get_content_type())
            body = deser.deserialize_create(request.body)

        # Add any checks for required elements/attributes/keys
        if not env['dbcontainer'].get('flavorRef', ''):
            raise exception.ApiError("Required attribute/key 'flavorRef' " \
                                     "was not specified")
        return env, body

    def _determine_root(self, req, container, id):
        """ Determine if root is enabled for a given container. """
        # If we can't determine if root is enabled for whatever reason,
        # including if the container isn't ACTIVE, rootEnabled isn't
        # available.
        running = _dbaas_mapping[power_state.RUNNING]
        if container['status'] == running:
            try:
                ctxt = req.environ['nova.context']
                return self.guest_api.is_root_enabled(ctxt, id)
            except Exception as err:
                LOG.error(err)
                LOG.error("rootEnabled for %s could not be determined." % id)
        return
