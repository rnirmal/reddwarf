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

import time

from nova.utils import LoopingCall
from nova.utils import LoopingCallDone

from reddwarf import exception


def poll_until(retriever, condition=lambda value: value,
               sleep_time=1, time_out=None):
    """Retrieves object until it passes condition, then returns it.

    If time_out_limit is passed in, PollTimeOut will be raised once that
    amount of time is eclipsed.

    """
    start_time = time.time()

    def poll_and_check():
        obj = retriever()
        if condition(obj):
            raise LoopingCallDone(retvalue=obj)
        if time_out is not None and time.time() > start_time + time_out:
            raise exception.PollTimeOut
    lc = LoopingCall(f=poll_and_check).start(sleep_time, True)
    return lc.wait()