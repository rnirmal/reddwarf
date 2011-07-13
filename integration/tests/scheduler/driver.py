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
from datetime import datetime

from nose.tools import assert_almost_equal
from nose.tools import assert_equal
from nose.tools import assert_not_almost_equal
from nose.tools import assert_true
from proboscis import test
from proboscis.decorators import expect_exception
from proboscis.decorators import time_out

#from tests.util import create_openstack_client
from nova.utils import poll_until
from tests import initialize
from tests.scheduler import SCHEDULER_DRIVER_GROUP
from tests.volumes import VOLUMES_DRIVER
from tests.util import create_dbaas_client
from tests.util import test_config
from tests.util import TestClient
from tests.util.users import Requirements


GROUP = SCHEDULER_DRIVER_GROUP

client = None
flavor_href = None
instance = None

@test(groups=[GROUP], depends_on_groups=["services.initialize"])
def setUp():
    """Set up vars needed by this story."""
    user = test_config.users.find_user(Requirements(is_admin=True))
    global client
    #client = TestClient(create_openstack_client(user))
    client = TestClient(create_dbaas_client(user))
    flavors = client.find_flavors_by_ram(ram=8192)
    assert_true(len(flavors) >= 1, "No flavor found!")
    flavor = flavors[0]
    global flavor_href
    flavor_href = client.find_flavor_self_href(flavor)


@test(groups=[GROUP], depends_on=[setUp])
def create_container():
    """Create the container. Expect the scheduler to fail the request."""
    #TODO(tim.simpson): Try to get this to work using a direct instance
    #                   creation call.
#    instance = instance_info.client.servers.create(
#        name="My Instance",
#        image=test_config.dbaas_image,
#        flavor=1
#    )
    global instance
    now = datetime.utcnow()
    instance = client.dbcontainers.create(
        "sch_test_" + str(now),
        flavor_href,
        {"size":1},
        [{"name": "firstdb", "charset": "latin2",
          "collate": "latin2_general_ci"}])


@test(groups=[GROUP], depends_on=[setUp])
def retrieve_container():
    """Retrieves the container. Expect it to have err'd."""
    evidence = "Error scheduling " + instance.name
    poll_until(lambda : file('/vagrant/nova.log', 'r').read(),
               lambda log : evidence in log, sleep_time=3, time_out=60)
    #TODO(tim.simpson) Pretty terrible! We'll need to fix this once the unhappy
    #                  path in scheduler does something more interesting.





