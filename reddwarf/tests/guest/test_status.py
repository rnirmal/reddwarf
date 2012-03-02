#    Copyright 2011 OpenStack LLC
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
Tests for reddwarf.compute.manager.
"""


import unittest

from eventlet.timeout import Timeout

from nova import db
from nova import context
from nova import exception
from nova import flags
from nova import test
from nova import utils
from nova.compute import instance_types
from nova.compute import vm_states
from reddwarf import exception as reddwarf_exception
from reddwarf.compute.api import API
from reddwarf.compute import manager
from reddwarf.compute.manager import ReddwarfComputeManager
from reddwarf.db import api as dbapi
from reddwarf.guest import status as guest_status
from reddwarf.guest.status import GuestStatus
from reddwarf.tests import util


FLAGS = flags.FLAGS


class TestWhenComparingTwoGuestStatusInstances(unittest.TestCase):

    def test_should_be_true_when_equal(self):
        self.assertTrue(guest_status.BUILDING == guest_status.BUILDING)
        self.assertFalse(guest_status.BUILDING != guest_status.BUILDING)
        self.assertEqual(guest_status.BUILDING, guest_status.BUILDING)

    def test_should_be_false_when_not_equal(self):
        self.assertFalse(guest_status.BUILDING == guest_status.RUNNING)
        self.assertTrue(guest_status.BUILDING != guest_status.RUNNING)
        self.assertNotEqual(guest_status.BUILDING, guest_status.RUNNING)

    def test_should_be_false_if_instance_of_other_type(self):
        self.assertFalse(guest_status.BUILDING == 5)
        self.assertFalse(5 == guest_status.BUILDING)
        self.assertTrue(5 != guest_status.BUILDING)
        self.assertTrue(guest_status.BUILDING != 5)


class TestWhenRetrievingGuestStatusByCode(unittest.TestCase):

    def test_should_work_with_valid_code(self):
        self.assertEqual(guest_status.CRASHED,
                         GuestStatus.from_code(guest_status.CRASHED.code))

    def test_should_raise_with_invalid_code(self):
        self.assertRaises(ValueError, GuestStatus.from_code, 84378)
        self.assertRaises(ValueError, GuestStatus.from_code, "0x02")