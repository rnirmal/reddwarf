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
Handles all requests to the DNS Manager.
"""


import numbers
import types

from nova import flags
from nova import log as logging
from nova import rpc
from nova.db import base
from nova.db.sqlalchemy.models import NovaBase

FLAGS = flags.FLAGS
flags.DEFINE_string('dns_topic', 'dns', 'the topic dns nodes listen on')

LOG = logging.getLogger('reddwarf.dns.api')


class API(base.Base):
    """API for interacting with the DNS manager."""

    def __init__(self, **kwargs):
        super(API, self).__init__(**kwargs)

    def convert_instance(self, instance):
        if isinstance(instance, NovaBase):
            new_instance = {}
            for k, v in instance:
                if isinstance(v, (types.BooleanType, numbers.Number,
                                  types.StringTypes)):
                    new_instance[k] = v
            return new_instance
        return instance

    def create_instance_entry(self, context, instance, content):
        """Make an asynchronous call to create a new entry for an instance."""
        converted_instance = self.convert_instance(instance)
        LOG.debug("Creating instance entry for instance %s, with content %s"
                  % (converted_instance, content))
        rpc.cast(context,  FLAGS.dns_topic,
                 {'method': 'create_instance_entry',
                  'args': {'instance': converted_instance,
                           'content': content}})

    def delete_instance_entry(self, context, instance, content):
        """Make an asynchronous call to delete an entry for an instance."""
        LOG.debug("Deleting instance entry for instance %s, with content %s"
                  % (instance, content))
        rpc.cast(context,  FLAGS.dns_topic,
                 {'method': 'delete_instance_entry',
                  'args': {'instance': self.convert_instance(instance),
                           'content': content}})
