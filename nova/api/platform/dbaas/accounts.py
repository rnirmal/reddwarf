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
from nova.api.openstack import faults
from nova.api.openstack import servers
from nova.api.openstack import wsgi
from nova.api.platform.dbaas import common
from nova.exception import NotFound
from nova.guest import api as guest
from reddwarf.db import api as dbapi

LOG = logging.getLogger('nova.api.platform.dbaas.accounts')
LOG.setLevel(logging.DEBUG)


FLAGS = flags.FLAGS

def create_resource(version='1.0'):
    controller = {
        '1.0': Controller,
    }[version]()

    metadata = {
        "attributes": {
            "account": ["name"],
            "hosts": ["id", "hostname", "name"],
            "dbcontainers": ["id", "status"],
        },
    }

    xmlns = {
        '1.0': common.XML_NS_V10,
    }[version]

    serializers = {
        'application/xml': wsgi.XMLDictSerializer(metadata=metadata,
                                                  xmlns=xmlns),
    }

    response_serializer = wsgi.ResponseSerializer(body_serializers=serializers)
    return wsgi.Resource(controller, serializer=response_serializer)


class Controller(object):
    """ The Account API controller for the Management API """

    def __init__(self):
        super(Controller, self).__init__()

    def show(self, req, id):
        """ Returns account details by account id """
        try:
            LOG.info("Get Account Details by ID - %s", id)
            LOG.debug("%s - %s", req.environ, req.body)
            context = req.environ['nova.context']

            # Check that the account exists by looking for its projects
            projects = db.project_get_by_user(context, id)
            LOG.debug("projects - %s", projects)
            if not projects:
                LOG.debug("Could not find any projects for account '%s'." % id)
                raise NotFound(message=("No Account found %s" % id))

            # Get all the containers that belong to this account.
            containers = dbapi.show_containers_by_account(context, id)
            LOG.debug("containers - %s", containers)

            # Prune away all the columns but the ones in key_list
            key_list = ['id', 'display_name', 'host', 'state']
            containers = [dict([(k, c[k]) for k in key_list])
                for c in containers]
            LOG.debug("containers - %s", containers)

            # Associate each unique host with its containers.
            unique_hosts = set([c['host'] for c in containers])
            LOG.debug("unique hosts - %s", unique_hosts)
            hosts = []
            for hostname in unique_hosts:
                host = {'id': hostname}
                hosts_containers = [c for c in containers
                    if c['host'] == hostname]
                hosts_containers = [{'id': c['id'],
                                     'name': c['display_name'],
                                     'status': c['state'],
                                    } for c in hosts_containers]
                hosts_containers = [{'dbcontainer': c}
                    for c in hosts_containers]
                host['dbcontainers'] = hosts_containers
                hosts.append(host)

            LOG.debug("hosts - %s", hosts)

            resp = {
                'account': {
                    'name': id,
                    'hosts': hosts
                    },
                }
            LOG.debug("resp - %s", resp)
            return resp
        except exception.NotFound as ex:
            return faults.Fault(exc.HTTPNotFound())
        except exception.UserNotFound as ex:
            return faults.Fault(exc.HTTPNotFound())
