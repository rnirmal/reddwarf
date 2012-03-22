# Copyright 2010-2011 OpenStack LLC.
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

import os


from nova import log as logging
from nova.api.openstack import common
from nova.api.openstack.views import flavors as os_flavors


LOG = logging.getLogger('reddwarf.api.flavors')
LOG.setLevel(logging.DEBUG)


class ViewBuilder(os_flavors.ViewBuilderV11):
    """Simpler view of flavors which removes local_gb."""

    def _build_detail(self, flavor_obj):
        """Build a more complete representation of a flavor."""
        LOG.debug("_build_detail of a flavor")
        flavor = self._build_simple(flavor_obj)

        flavor['ram'] = flavor_obj['memory_mb']
        flavor['vcpus'] = flavor_obj['vcpus']

        return flavor

    def _build_links(self, flavor_obj):
        """Generate a container of links that refer to the provided flavor."""

        # rewrite the urls to https because internal systems may rewrite
        # them to http when they are in fact https.
        self.base_url = str(self.base_url).replace('http:', 'https:')

        href = os.path.join(self.base_url, self.project_id, "flavors", str(flavor_obj['id']))
        bookmark = os.path.join(common.remove_version_from_href(self.base_url),
                                "flavors", str(flavor_obj['id']))

        links = [
            {
                'rel': 'self',
                'href': href
            },
            {
                "rel": "bookmark",
                "href": bookmark,
            },
        ]
        return links
