# Copyright 2011 OpenStack LLC.
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

from nova import flags
from nova import log as logging
from nova.notifier import log_notifier

FLAGS = flags.FLAGS
flags.DEFINE_string('notifier_logfile', None,
                    'Separate log file for notifications, off by default')


if FLAGS.notifier_logfile:
    logger = logging.getLogger("nova.notification")
    handler = logging.WatchedFileHandler(FLAGS.notifier_logfile)
    logger.addHandler(handler)


def notify(message):
    """Notifies the recipient of the desired event given the model.
    Log notifications using nova's default logging system"""
    log_notifier.notify(message)
