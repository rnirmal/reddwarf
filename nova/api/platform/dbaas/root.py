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
from nova.api.platform.dbaas import common
from nova.guest import api as guest_api
from nova.guest.db import models


LOG = logging.getLogger('nova.api.platform.dbaas.root')
LOG.setLevel(logging.DEBUG)


class Controller(common.DBaaSController):
    """ Enable/Disable the root user for the DB Container """

    _serialization_metadata = {
        'application/xml': {
            'attributes': {
                'user': ['name', 'password']
            },
        },
    }

    def __init__(self):
        self.guest_api = guest_api.API()
        self.compute_api = compute.API()
        super(Controller, self).__init__()

    def delete(self, req, dbcontainer_id):
        """ Disables the root user in the db container """
        LOG.info("Call to disable root user for container %s", dbcontainer_id)
        LOG.debug("%s - %s", req.environ, req.body)
        ctxt = req.environ['nova.context']
        common.instance_exists(ctxt, dbcontainer_id, self.compute_api)

        try:
            self.guest_api.disable_root(ctxt, dbcontainer_id)
            return exc.HTTPOk()
        except Exception as err:
            LOG.error(err)
            return exc.HTTPError("Error disabling the root password")

    def create(self, req, dbcontainer_id):
        """ Enable the root user for the db container """
        LOG.info("Call to enable root user for container %s", dbcontainer_id)
        LOG.debug("%s - %s", req.environ, req.body)
        ctxt = req.environ['nova.context']
        common.instance_exists(ctxt, dbcontainer_id, self.compute_api)

        try:
            result = self.guest_api.enable_root(ctxt, dbcontainer_id)
            user = models.MySQLUser()
            user.deserialize(result)
            return {'user': {'name': user.name, 'password': user.password}}
        except Exception as err:
            LOG.error(err)
            return exc.HTTPError("Error enabling the root password")

    def is_root_enabled(self, req, dbcontainer_id):
        """ Returns True if root is enabled for the given container;
            False otherwise. """
        LOG.info("Call to is_root_enabled for container %s", dbcontainer_id)
        LOG.debug("%s - %s", req.environ, req.body)
        ctxt = req.environ['nova.context']
        common.instance_exists(ctxt, dbcontainer_id, self.compute_api)

        try:
            result = self.guest_api.is_root_enabled(ctxt, dbcontainer_id)
            return {'root_enabled': result}
        except Exception as err:
            LOG.error(err)
            return exc.HTTPError("Error determining root access")
