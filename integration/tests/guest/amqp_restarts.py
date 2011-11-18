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

from proboscis.asserts import assert_equal
from proboscis.asserts import assert_false
from proboscis.asserts import assert_true
from nova import context
from os import path
from nova.exception import ProcessExecutionError
from nova import rpc
from tests.util.services import Service
import string
from proboscis import test
from tests.util import test_config
import time
from nova import utils
from tests import util as test_utils


# Kill Rabbit
# Start guest
# Make sure Guest aint dead
# Start rabbit
# Send message, ensure we get a response
# Kill rabbit
# Clear all queues
# Start rabbit
# Send message, ensure we get a response
# Kill guest and clean up


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

    @test
    def check_agent_path_is_correct(self):
        """Make sure the agent binary listed in the config is correct."""
        agent_bin = str(test_config.values["agent_bin"])
        nova_conf = str(test_config.values["nova_conf"])
        assert_true(path.exists(agent_bin),
                    "Agent not found at path: %s" % agent_bin)
        self.agent = Service(cmd=[agent_bin,  "--flagfile=%s" % nova_conf,
                                  "--rabbit_reconnect_wait_time=1"])
        self.rabbit = Rabbit()

    @test
    def stop_rabbit(self):
        if self.rabbit.is_alive:
            self.rabbit.stop()
        assert_false(self.rabbit.is_alive)
        self.rabbit.reset()

    @test(depends_on=[check_agent_path_is_correct, stop_rabbit])
    def start_agent(self):
        self.agent.start()
        mem = self.agent.get_memory_info()
        self.original_mapped = mem.mapped

    @test(depends_on=[start_agent])
    def memory_should_not_increase_as_amqp_login_fails(self):
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
        time.sleep(5)
        current_mapped = self.agent.get_memory_info().mapped
        assert_true(current_mapped <= self.original_mapped)

    @test(depends_on=[memory_should_not_increase_as_amqp_login_fails])
    def start_rabbit(self):
        self.rabbit.start()
        assert_true(self.rabbit.is_alive)

    @test(depends_on=[start_rabbit])
    def send_message(self):
        version = rpc.call(context.get_admin_context(), "guest.host",
                 {"method": "version",
                  "args": {"package": "cowsay"}
                 })
        assert_true(version is not None)
        

#TODO: Test when the login fails due to low memory, the agent memory does not
# shoot up.




