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
Set of utilities for the Guest Manager
"""

import socket

instance_id = None


def get_instance_id():
    """Return the instance id for this guest"""
    global instance_id
    if not instance_id:
        # TODO(rnirmal): Better way to get the instance id
        hostname = socket.gethostname()
        instance_id = hostname.split("-")[1]
    return instance_id
