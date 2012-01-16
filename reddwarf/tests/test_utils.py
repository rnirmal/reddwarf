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

from nova import test

from reddwarf import exception
from reddwarf.utils import poll_until


class PollUntilTestCase(test.TestCase):

    def test_when_timeout_occurs(self):
        self.assertRaises(exception.PollTimeOut, poll_until, lambda: 5,
                          lambda n: n != 5, sleep_time=0, time_out=1)

    def test_when_timeout_does_not_occur(self):
        number = poll_until(lambda: 7, lambda n: n != 5, sleep_time=0,
                            time_out=1)
        self.assertNotEqual(5, number)

    def test_without_timeout(self):
        class NumberService(object):

            def __init__(self):
                self.number = 0

            def get_number(self):
                self.number += 10
                return self.number

        service = NumberService()
        result = poll_until(service.get_number, lambda n: n > 50,
                            sleep_time=0)
        self.assertEqual(60, result)

