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


import unittest

from nose.tools import assert_equal
from nose.tools import assert_false
from nose.tools import assert_true

from proboscis import test
from tests.util import create_test_client
from tests.util import test_config
from tests.util.users import Requirements


GROUP="dbaas.flavors"


servers_flavors=None
dbaas_flavors=None
user=None


def assert_attributes_are_equal(name, os_flavor, dbaas_flavor):
    """Given an attribute name and two objects ensures the attribute is equal."""
    assert_true(hasattr(os_flavor, name),
                "open stack flavor did not have attribute %s" % name)
    assert_true(hasattr(dbaas_flavor, name),
                "open stack flavor did not have attribute %s" % name)
    expected = getattr(os_flavor, name)
    actual = getattr(dbaas_flavor, name)
    assert_equal(expected, actual,
                 'DBaas flavor differs from Open Stack on attribute ' + name)

def assert_flavors_are_roughly_equivalent(os_flavor, dbaas_flavor):
    assert_attributes_are_equal('name', os_flavor, dbaas_flavor)
    assert_attributes_are_equal('ram', os_flavor, dbaas_flavor)
    assert_false(hasattr(dbaas_flavor, 'disk'),
                 "The attribute 'disk' s/b absent from the dbaas API.")
    assert_link_list_is_equal(os_flavor, dbaas_flavor)

def assert_link_list_is_equal(os_flavor, dbaas_flavor):
    assert_true(hasattr(dbaas_flavor, 'links'))
    assert_equal(len(os_flavor.links), len(dbaas_flavor.links))
    # Unlike other resource objects, the links are dictionaries that don't
    # have fake attributes.
    for os_link in os_flavor.links:
        found_index = None
        assert_true('rel' in os_link, "rel should be in OS flavor, right?")
        for index, dbaas_link in enumerate(dbaas_flavor.links):
            assert_true('rel' in dbaas_link, "rel should be in DBAAS flavor.")
            if os_link['rel'] == dbaas_link['rel']:
                assert_true(found_index is None,
                            "rel %s appears in elements #%s and #%d." % \
                            (str(dbaas_link['rel']), str(found_index), index))
                assert_true('href' in os_link, "'href s /b in os link.")
                assert_true('href' in dbaas_link, "'href s /b in dbaas link.")
                nova_url_len = len(test_config.nova.url)
                os_relative_href = os_link['href'][nova_url_len:]
                dbaas_url_len = len(test_config.dbaas.url)
                dbaas_relative_href = dbaas_link['href'][dbaas_url_len:]
                assert_equal(os_relative_href, dbaas_relative_href,
                             '"href" must be same if "rel" matches.')
                found_index = index
        assert_false(found_index is None,
                     "Some links from OS list were missing in DBAAS list.")

@test(groups=[GROUP], depends_on_groups=["services.initialize"])
def confirm_flavors_lists_are_nearly_identical():
    """Confirms dbaas.flavors mirror server flavors aside from some caveats."""
    user = test_config.users.find_user(Requirements(is_admin=True))
    global client
    client = create_test_client(user)
    os_flavors = client.os.flavors.list()
    dbaas_flavors = client.dbaas.flavors.list()

    print("Open Stack Flavors:")
    print(os_flavors)
    print("DBaaS Flavors:")
    print(dbaas_flavors)
    assert_equal(len(os_flavors), len(dbaas_flavors),
                 "Length of both flavors list should be identical.")
    for os_flavor in os_flavors:
        found_index = None
        for index, dbaas_flavor in enumerate(dbaas_flavors):
            if os_flavor.id == dbaas_flavor.id:
                assert_true(found_index is None,
                            "Flavor ID %d appears in elements #%s and #%d." %\
                            (dbaas_flavor.id, str(found_index), index))
                assert_flavors_are_roughly_equivalent(os_flavor, dbaas_flavor)
                found_index = index
        assert_false(found_index is None,
                     "Some flavors from OS list were missing in DBAAS list.")
