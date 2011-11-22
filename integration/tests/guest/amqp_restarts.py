# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
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

"""Tests the agents ability to withstand connection loss.

This test takes down rabbit and brings it back up while running the guest and
not restarting it. It tests that the Guest handle Rabbit going down and coming
back up.

"""

import re
import string
import time

from os import path

from proboscis import after_class
from proboscis.asserts import assert_equal
from proboscis.asserts import assert_false
from proboscis.asserts import assert_true
from proboscis.asserts import fail
from proboscis.decorators import time_out
from proboscis import test


from nova import context
from nova import rpc
from nova import utils
from nova.exception import ProcessExecutionError
from tests import util as test_utils
from tests.util import test_config
from tests.util.services import Service


class Rabbit(object):


    @property
    def is_alive(self):
        """Calls list_queues, should fail."""
        try:
            self.run(0, "rabbitmqctl", "list_queues")
            return True
        except ProcessExecutionError:
            return False

    def reset(self):
        self.run(0, "rabbitmqctl", "reset")

    def run(self, check_exit_code, *cmd):
        utils.execute(*cmd, run_as_root=True)

    def start(self):
        self.run(0, "rabbitmqctl", "start_app")

    def stop(self):
        self.run(0, "rabbitmqctl", "stop_app")


@test(groups=["agent", "amqp.restarts"])
class WhenAgentRunsAsRabbitGoesUpAndDown(object):
    """Tests the agent is ok when Rabbit 
    """

    @after_class
    def stop_agent(self):
        self.agent.stop

    @test
    def check_agent_path_is_correct(self):
        """Make sure the agent binary listed in the config is correct."""
        self.agent_bin = str(test_config.values["agent_bin"])
        nova_conf = str(test_config.values["nova_conf"])
        assert_true(path.exists(self.agent_bin),
                    "Agent not found at path: %s" % self.agent_bin)
        self.agent = Service(cmd=[self.agent_bin,  "--flagfile=%s" % nova_conf,
                                  "--rabbit_reconnect_wait_time=1"])

    @test
    def stop_rabbit(self):
        self.rabbit = Rabbit()
        if self.rabbit.is_alive:
            self.rabbit.stop()
        assert_false(self.rabbit.is_alive)
        self.rabbit.reset()

    @test(depends_on=[check_agent_path_is_correct, stop_rabbit])
    def start_agent(self):
        """Starts the agent as rabbit is stopped.

        Checks to make sure the agent doesn't just give up if it can't connect
        to Rabbit, and also that the memory doesn't grow as it increasingly
        creates connections.

        """
        self.agent.start()
        mem = self.agent.get_memory_info()
        self.original_mapped = mem.mapped

    @test(depends_on=[start_agent])
    def memory_should_not_increase_as_amqp_login_fails(self):
        """The agent should not spend memory on failed connections."""
        #TODO(tim.simpson): This operates on the assumption that the the agent
        # will try to reconnect multiple times while we sleep.
        # Explanation: the syslog (where the agent logs now reside) is
        # unreadable by the test user, so we can't count the original
        # failures and wait until we know the agent has tried to reconnect
        # several times before testing again. Instead we just sleep.
        # Once we log to a readable file we should fix that.
        #self.original_fail_count = count_message_occurrence_in_file(
        #    "/var/log/syslog", "Error establishing AMQP connection"
        #)
        # Memory should not go up as the connection fails.
        print("Original mapped memory        : %d" % self.original_mapped)

        # I've noticed that the memory jumps up a bit between 5 and 10 seconds
        # after it starts and then holds steady. So instead of taking the
        # original count, let's wait a bit and use that.
        time.sleep(10)
        self.original_mapped = self.agent.get_memory_info().mapped
        print("Mapped memory at 10 seconds   : %d" % self.original_mapped)

        total_seconds = 0
        mapped = []
        for i in range(4):
            time.sleep(5)
            total_seconds += 5
            mapped.append(self.agent.get_memory_info().mapped)
            print("Mapped memory after %d seconds : %d"
                  % (total_seconds, mapped[-1]))
        if self.original_mapped < mapped[-1]:
            fail("Oh no, after %d seconds memory rose from %d to %d!"
                 % (total_seconds, self.original_mapped, mapped[-1]))
        if mapped[-1] > 30 * 1024:
            fail("Whoa, why is mapped memory = %d for procid=%d, proc= %s?"
                 % (current_mapped, self.agent.find_proc_id(), self.agent_bin))

    @test(depends_on=[memory_should_not_increase_as_amqp_login_fails])
    def start_rabbit(self):
        """Start rabbit."""
        self.rabbit.start()
        assert_true(self.rabbit.is_alive)

    @test(depends_on=[start_rabbit])
    def send_message(self):
        """Tests that the agent auto-connects to rabbit and gets a message."""
        version = rpc.call(context.get_admin_context(), "guest.host",
                 {"method": "version",
                  "args": {"package_name": "dpkg"}
                 })
        assert_true(version is not None)
        matches = re.search("(\\w+)\\.(\\w+)\\.(\\w+)\\.(\\w+)", version)
        assert_true(matches is not None)

    @test(depends_on=[send_message])
    def restart_rabbit_again(self):
        """Now stop and start rabbit, ensuring the agent reconnects."""
        self.rabbit.stop()
        assert_false(self.rabbit.is_alive)
        self.rabbit.reset()
        self.rabbit.start()
        assert_true(self.rabbit.is_alive)
        self.reconnect_failures_count = 0

    @test(depends_on=[restart_rabbit_again])
    @time_out(2)
    def send_message_again_1(self):
        """Sends a message.

        In the Kombu driver there is a bug where after restarting rabbit the
        first message to be sent fails with a broken pipe (Carrot has a worse
        bug where the tests hang). So here we tolerate one such bug but no
        more.

        """
        try:
            self.send_message()
            fail("Looks like the Kombu bug was fixed, please change this code "
                 "to except no Exceptions.")
        except Exception:
            self.reconnect_failures_count += 1
            assert_equal(1, self.reconnect_failures_count)

    @test(depends_on=[send_message_again_1])
    @time_out(2)
    def send_message_again_2a(self):
        """The agent should be able to receive messages after reconnecting."""
        self.send_message()

    @test(depends_on=[send_message_again_1])
    @time_out(2)
    def send_message_again_2b(self):
        """The agent should be able to receive messages after reconnecting."""
        self.send_message()




