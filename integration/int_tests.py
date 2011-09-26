#!/usr/bin/env python
# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# # Copyright (c) 2011 OpenStack, LLC.
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


"""Runs the tests.

This script imports all other tests to make them known to Proboscis before
passing control to proboscis.TestProgram.

"""


from __future__ import absolute_import
import atexit
import gettext
import os
import time
import unittest
import sys


def add_support_for_localization():
    """Adds support for localization in the logging.

    If ../nova/__init__.py exists, add ../ to Python search path, so that
    it will override what happens to be installed in
    /usr/(local/)lib/python...

    """
    path = os.path.join(os.path.abspath(sys.argv[0]), os.pardir, os.pardir)
    possible_topdir = os.path.normpath(path)
    if os.path.exists(os.path.join(possible_topdir, 'nova', '__init__.py')):
        sys.path.insert(0, possible_topdir)

    gettext.install('nova', unicode=1)


def _clean_up():
    """Shuts down any services this program has started."""
    from tests.util.services import get_running_services
    for service in get_running_services():
        sys.stderr.write("Stopping service " + str(service.cmd) + "...\n\r")
        service.stop()


if __name__ == '__main__':

    add_support_for_localization()

    # Strip non-nose arguments out before passing this to nosetests
    nose_args = []
    conf_file = "~/nemesis.conf"
    show_elapsed = True
    groups = []
    for arg in sys.argv[1:]:
        if arg[:7] == "--conf=":
            conf_file = os.path.expanduser(arg[7:])
            print("Setting NEMESIS_CONF to " + conf_file)
            os.environ["NEMESIS_CONF"] = conf_file
        elif arg[:8] == "--group=":
            groups.append(arg[8:])
        elif arg[:11] == "--flagfile=":
            pass  # Don't append this...
        elif arg.startswith('--hide-elapsed'):
            show_elapsed = False
        else:
            nose_args.append(arg)

    # TODO(tim.simpson):
    # Before Proboscis was at its current state, it was necessary to load the
    # configuration as an environment variable because decorators where used
    # to show tests depended on running services, and these needed the
    # configuration values.  However, now there is probably a better way to
    # handle this than forcing this to be imported after the environment
    # variable is set.

    # Set up the flag file values, which we need to call certain Nova code.
    from tests.util import test_config
    nova_conf = test_config.values["nova_conf"]

    from nova import utils
    utils.default_flagfile(str(nova_conf))
    
    from nova import flags
    FLAGS = flags.FLAGS
    FLAGS(sys.argv)

    # Now that the FlagFiles and other args have been parsed, time to import
    # everything.

    import proboscis
    from tests.dns import check_domain
    from tests.dns import conversion

    # The DNS stuff is problematic. Not loading the other tests allow us to
    # run its functional tests only.
    if not os.environ.get("ADD_DOMAINS", "False") == 'True':
        from tests import initialize
        from tests.dbaas import dbaas_ovz
        from tests.dbaas import dns
        from tests.dbaas import flavors
        from tests.guest import dbaas_tests
        from tests.guest import pkg_tests
        from tests.reaper import volume_reaping
        from tests.scheduler import driver
        from tests.scheduler import SCHEDULER_DRIVER_GROUP
        from tests.volumes import driver
        from tests.volumes import VOLUMES_DRIVER
        from tests.dbaas import guest_initialize_failure

        from tests import util

        host_ovz_groups = [
            "dbaas.guest",
            "dbaas.guest.dns",
            SCHEDULER_DRIVER_GROUP,
            pkg_tests.GROUP,
            VOLUMES_DRIVER,
            guest_initialize_failure.GROUP,
            volume_reaping.GROUP
        ]
        if util.should_run_rsdns_tests():
            host_ovz_groups += ["rsdns.conversion", "rsdns.domains"]

        proboscis.register(groups=["host.ovz"], depends_on_groups=host_ovz_groups)

    atexit.register(_clean_up)

    # Set up pretty colors.

    from nose import config
    from nose import core
    from run_tests import NovaTestResult
    from run_tests import NovaTestRunner
    from proboscis.case import TestResult as ProboscisTestResult

    class IntegrationTestResult(NovaTestResult, ProboscisTestResult):

        def addFailure(self, test, err):
            self.onError(test)
            super(IntegrationTestResult, self).addFailure(test, err)

        def addError(self, test, err):
            self.onError(test)
            super(IntegrationTestResult, self).addError(test, err)

        @staticmethod
        def get_doc(cls_or_func):
            """Grabs the doc abbreviated doc string."""
            try:
                return cls_or_func.__doc__.split("\n")[0].strip()
            except (AttributeError, IndexError):
                return None

        def startTest(self, test):
            unittest.TestResult.startTest(self, test)
            self.start_time = time.time()
            test_name = None
            try:
                entry = test.test.__proboscis_case__.entry
                if entry.method:
                    current_class = entry.method.im_class
                    test_name = self.get_doc(entry.home) or entry.home.__name__
                else:
                    current_class = entry.home
            except AttributeError:
                current_class = test.test.__class__

            if self.showAll:
                if current_class.__name__ != self._last_case:
                    self.stream.writeln(current_class.__name__)
                    self._last_case = current_class.__name__
                    try:
                        doc = self.get_doc(current_class)
                    except (AttributeError, IndexError):
                        doc = None
                    if doc:
                        self.stream.writeln(' ' + doc)

                if not test_name:
                    if hasattr(test.test, 'shortDescription'):
                        test_name = test.test.shortDescription()
                    if not test_name:
                        test_name = test.test._testMethodName
                self.stream.write('    %s' %
                    '    %s' % str(test_name).ljust(60))
                self.stream.flush()


    class IntegrationTestRunner(NovaTestRunner):
        
        def _makeResult(self):
            return IntegrationTestResult(self.stream,
                                         self.descriptions,
                                         self.verbosity,
                                         self.config,
                                         show_elapsed=self.show_elapsed)

    testdir = os.path.abspath(os.path.join("nova", "integration", "tests"))
    c = config.Config(stream=sys.stdout,
                      env=os.environ,
                      verbosity=3,
                      workingDir=testdir,
                      plugins=core.DefaultPluginManager())
    runner = IntegrationTestRunner(stream=c.stream,
                                   verbosity=c.verbosity,
                                   config=c,
                                   show_elapsed=show_elapsed)

    proboscis.TestProgram(argv=nose_args, groups=groups,
                          testRunner=runner).run_and_exit()
