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
from nova.api.openstack import wsgi
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
flags.DEFINE_string('reddwarf_mysql_data_dir', '/var/lib/mysql',
                    'Mount point within the container for MySQL data.')

_dbaas_mapping = {
    None: 'BUILD',
    power_state.NOSTATE: 'BUILD',
    power_state.RUNNING: 'ACTIVE',
    power_state.SHUTDOWN: 'SHUTDOWN',
    power_state.BUILDING: 'BUILD'
}


class Controller(object):
    """ The DBContainer API controller for the Platform API """

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
        return resp

    @staticmethod
    def get_guest_state_mapping(resp):
        """Returns a dictionary of guest statuses keyed by guest ids."""
        ids = [dbcontainer['id'] for dbcontainer in resp['dbcontainers']]
        results = dbapi.guest_status_get_list(ids)
        return dict([(r.instance_id, r.state) for r in results])

    def detail(self, req):
        """ Returns a list of dbcontainer details for a given user """
        LOG.debug("%s - %s", req.environ, req.body)
        resp = {'dbcontainers': self.server_controller.detail(req)['servers']}
        #resp = self._manipulate_response(req, resp)
        guest_state_mapping = self.get_guest_state_mapping(resp)
        for container in resp['dbcontainers']:
            self._modify_fields(req, container)
            # We're making the assumption we can pull the status from the
            # returned instance info.
            self._modify_status(response=container, instance_info=container,
                                guest_states=guest_state_mapping)
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
        dbcontainer = resp['dbcontainer']
        self._modify_fields(req, dbcontainer)
        self._modify_status(response=dbcontainer, instance_info=dbcontainer)
        enabled = self._determine_root(req, resp['dbcontainer'], id)
        if enabled is not None:
            resp['dbcontainer']['rootEnabled'] = enabled
        return resp

    def delete(self, req, id):
        """ Destroys a dbcontainer """
        LOG.info("Delete Container by ID - %s", id)
        LOG.debug("%s - %s", req.environ, req.body)
        context = req.environ['nova.context']

        self.server_controller.delete(req, id)
        #TODO(rnirmal): Use a deferred here to update status
        dbapi.guest_status_delete(id)
        try:
            for volume_ref in db.volume_get_all_by_instance(context, id):
                self.volume_api.delete_volume_when_available(context,
                                                             volume_ref['id'],
                                                             time_out=60)
        except exception.VolumeNotFoundForInstance:
            LOG.info("Skipping as no volumes are associated with the instance")

    def create(self, req, body):
        """ Creates a new DBContainer for a given user """
        self._validate(body)

        LOG.info("Create Container")
        LOG.debug("%s - %s", req.environ, body)

        # Create the Volume before hand
        volume_ref = self.create_volume(req, body)
        # Setup Security groups
        self._setup_security_groups(req,
                                    FLAGS.default_firewall_rule_name,
                                    FLAGS.default_guest_mysql_port)

        databases = common.populate_databases(
                                    body['dbcontainer'].get('databases', ''))

        # Add any extra data that's required by the servers api
        self._append_on_create(body, volume_ref['id'],
                               FLAGS.reddwarf_mysql_data_dir)
        server = self._try_create_server(req, self._rename_to_server(body))
        server_id = str(server['server']['id'])
        dbapi.guest_status_create(server_id)

        # Send the prepare call to Guest
        self.guest_api.prepare(req.environ['nova.context'],
                               server_id, databases)
        resp = {'dbcontainer': server['server']}
        self._modify_fields(req, resp['dbcontainer'])

        # add the volume information to response
        LOG.debug("adding the volume information to the response...")
        resp['dbcontainer']['volume'] = {'size': volume_ref['size']}

        return resp

    @staticmethod
    def _append_on_create(body, volume_id, mount_point):
        """Append additional stuff to create"""
        # Add image_ref
        body['dbcontainer']['imageRef'] = FLAGS.reddwarf_imageRef
        # Add Firewall rules
        firewall_rules = [FLAGS.default_firewall_rule_name]
        body['dbcontainer']['firewallRules'] = firewall_rules
        # Add volume id
        if not 'metadata' in body['dbcontainer']:
            body['dbcontainer']['metadata'] = {}
        body['dbcontainer']['metadata']['volume_id'] = str(volume_id)
        # Add mount point
        body['dbcontainer']['metadata']['mount_point'] = str(mount_point)

    @staticmethod
    def _rename_to_server(body):
        """Rename dbcontainer to server"""
        return {'server': body['dbcontainer']}

    def create_volume(self, req, body):
        """Creates the volume for the container and returns its ID."""
        context = req.environ['nova.context']
        try:
            volume_size = body['dbcontainer']['volume']['size']
        except KeyError as e:
            LOG.error("Create Container Required field(s) - %s" % e)
            raise exc.HTTPBadRequest("Create Container Required field(s) - %s"
                                     % e)

        return self.volume_api.create(context, size=volume_size,
                                      snapshot_id=None,
                                      name=None,
                                      description=None)

    def _try_create_server(self, req, body):
        """Handle the call to create a server through the openstack servers api.

        Separating this so we could do retries in the future and other
        processing of the result etc.
        """
        try:
            server = self.server_controller.create(req, body)
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
        user_id = context.user_id
        instance_info = {"id": response["id"], "user_id": user_id}
        dns_entry = self.dns_entry_factory.create_entry(instance_info)
        if dns_entry:
            hostname = dns_entry.name
            response["hostname"] = hostname

        LOG.debug("Removing the excess information from the containers.")
        for attr in ["hostId", "imageRef", "metadata", "adminPass", "uuid"]:
            if response.has_key(attr):
                del response[attr]
        if "volumes" in response:
            LOG.debug("Removing the excess information from the volumes.")
            for volume_ref in response["volumes"]:
                for attr in ["id", "name", "description"]:
                    if attr in volume_ref:
                        del volume_ref[attr]
                #set the last volume to our volume information (only 1)
                response["volume"] = volume_ref
            del response["volumes"]
        return response

    @staticmethod
    def _modify_status(response, instance_info, guest_states=None):
        # Status is set by first checking the compute instance status and
        # then the guest status. "guest_states" is a dictionary of
        # guest states mapped by guest ids.
        id = response['id']
        if instance_info['status'] == 'ERROR':
            response['status'] = 'ERROR'
        else:
            try:
                if guest_states:
                    state = guest_states[id]
                else:
                    state = dbapi.guest_status_get(id).state
            except (KeyError, InstanceNotFound):
                # we set the state to shutdown if not found
                state = power_state.SHUTDOWN
            response['status'] = _dbaas_mapping[state]

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

        if not db.security_group_exists(context, context.project_id,
                                        group_name):
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
            db.security_group_rule_create(context, rules)
            self.compute_api.trigger_security_group_rules_refresh(context,
                                                          security_group['id'])

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

    @staticmethod
    def _validate(body):
        """Validate that the request has all the required parameters"""
        if not body:
            return faults.Fault(exc.HTTPUnprocessableEntity())

        if not body.get('dbcontainer', ''):
            raise exception.ApiError("Required element/key 'dbcontainer' " \
                                      "was not specified")
        if not body['dbcontainer'].get('flavorRef', ''):
            raise exception.ApiError("Required attribute/key 'flavorRef' " \
                                     "was not specified")


def create_resource(version='1.0'):
    controller = {
        '1.0': Controller,
    }[version]()

    metadata = {
        "attributes": {
            "dbcontainer": ["id", "name", "status", "flavorRef", "rootEnabled"],
            "dbtype": ["name", "version"],
            "link": ["rel", "type", "href"],
            "volume": ["size"],
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
        'application/xml': deserializer.DBContainerXMLDeserializer(),
    }

    response_serializer = wsgi.ResponseSerializer(body_serializers=serializers)
    request_deserializer = wsgi.RequestDeserializer(body_deserializers=deserializers)

    return wsgi.Resource(controller, deserializer=request_deserializer,
                         serializer=response_serializer)
