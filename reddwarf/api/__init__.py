# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright (c) 2011 OpenStack, LLC.
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

"""
WSGI middleware for DBaaS API controllers.
"""

import routes

from nova import flags
from nova import log as logging
from nova import wsgi
from nova.api.openstack import images
from reddwarf.api import accounts
from reddwarf.api import databases
from reddwarf.api import instances
from reddwarf.api import guests
from reddwarf.api import hosts
from reddwarf.api import management
from reddwarf.api import root
from reddwarf.api import storage
from reddwarf.api import users
from reddwarf.api import flavors
from reddwarf.api import versions

LOG = logging.getLogger('reddwarf.api')
FLAGS = flags.FLAGS

flags.DEFINE_integer('default_guest_mysql_port', 3306,
                     'Default port used for guest mysql instance')
flags.DEFINE_string('default_firewall_rule_name',
                    'tcp_%s' %  FLAGS.default_guest_mysql_port,
                    'Default firewall rule name used for guest instances')
flags.DEFINE_string('nova_api_version', '1.1',
                    'The default nova api version for reddwarf')

class APIMapper(routes.Mapper):
    """
    Handles a Routes bug that drops an error for version requests that don't end in /
    If and when
    https://github.com/openstack/nova/commit/000174461a96ca70c76c8f3a85d9bf25fe673a2d
    gets merged in, this class can be replaced with the one in the commit.
    """
    def routematch(self, url=None, environ=None):
        if url is "":
            result = self._match("", environ)
            return result[0], result[1]
        return routes.Mapper.routematch(self, url, environ)

class APIRouter(wsgi.Router):
    """
    Routes requests on the DBaaS API to the appropriate controller
    and method.
    """

    @classmethod
    def factory(cls, global_config, **local_config):
        """Simple paste factory, :class:`nova.wsgi.Router` doesn't have one"""
        return cls()

    def __init__(self):
        mapper = APIMapper()

        instance_members = {'action': 'POST'}
        if FLAGS.allow_admin_api:
            LOG.debug(_("Including admin operations in API."))
            with mapper.submapper(path_prefix="/mgmt/guests",
                                  controller=guests.create_resource()) as m:
                m.connect("/upgradeall", action="upgradeall",
                          conditions=dict(method=["POST"]))
                m.connect("/{id}/upgrade", action="upgrade",
                          conditions=dict(method=["POST"]))

            mapper.resource("image", "images",
                            controller=images.create_resource(FLAGS.nova_api_version),
                            collection={'detail': 'GET'})

            with mapper.submapper(path_prefix="/mgmt/hosts",
                                  controller=hosts.create_resource()) as m:
                m.connect("", action="index",
                          conditions=dict(method=["GET"]))
                m.connect("/{id}", action="show",
                          conditions=dict(method=["GET"]))

            mapper.connect("/mgmt/instances/{id}",
                            controller=management.create_resource(),
                            action="show", conditions=dict(method=["GET"]))

            mapper.connect("/mgmt/instances/{id}/root",
                            controller=management.create_resource(),
                            action="root_enabled_history", conditions=dict(method=["GET"]))

            mapper.connect("/mgmt/storage",
                            controller=storage.create_resource(),
                            action="index", conditions=dict(method=["GET"]))

            mapper.connect("/mgmt/accounts/{id}",
                            controller=accounts.create_resource(),
                            action="show", conditions=dict(method=["GET"]))

            #TODO(rnirmal): Right now any user can access these
            # functions as long as the allow_admin_api flag is set.
            # Need to put something in place so that only real admin
            # users can hit that api, others would just be rejected.

        mapper.resource("instance", "instances",
                        controller=instances.create_resource(),
                        collection={'detail': 'GET'},
                        member=instance_members)

        mapper.resource("flavor", "flavors",
                        controller=flavors.create_resource(),
                        collection={'detail': 'GET'})

        mapper.resource("database", "databases",
                        controller=databases.create_resource(),
                        parent_resource=dict(member_name='instance',
                        collection_name='instances'))

        mapper.resource("user", "users",
                        controller=users.create_resource(),
                        parent_resource=dict(member_name='instance',
                        collection_name='instances'))

        # Using connect instead of resource due to the incompatibility
        # for delete without providing an id.
        mapper.connect("/instances/{instance_id}/root",
                       controller=root.create_resource(),
                       action="create", conditions=dict(method=["POST"]))
        mapper.connect("/instances/{instance_id}/root",
                       controller=root.create_resource(),
                       action="is_root_enabled", conditions=dict(method=["GET"]))

        mapper.connect("/", controller=versions.create_resource(),
                       action="dispatch")

        # Instead of dropping out with a Routes fault, we gently redirect
        # with a 302 to "/vX.Y/", our current version.
        mapper.redirect("", "/")

        super(APIRouter, self).__init__(mapper)
