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

import os
import shutil
from paste import urlmap

from nova import context
from nova import flags
from nova.api import openstack
from nova.api import auth as api_auth
from nova.api.openstack import limits
from nova.api.openstack import auth

import reddwarf
from reddwarf.db import migration
from reddwarf import tests as testinit

FLAGS = flags.FLAGS


def reset_database():
    """Reset the sqlite database for other test to use it"""
    if os.path.exists(testinit.database_file):
        os.remove(testinit.database_file)
    shutil.copy(testinit.clean_db, testinit.database_file)


def db_sync():
    migration.db_sync()


def wsgi_app(fake_auth=True, fake_auth_context=None):
    app = reddwarf.api.APIRouter()

    if fake_auth:
        if fake_auth_context is not None:
            ctxt = fake_auth_context
        else:
            ctxt = context.RequestContext('fake', 'fake', auth_token=True)
        api10 = openstack.FaultWrapper(api_auth.InjectContext(ctxt,
              limits.RateLimitingMiddleware(app)))
    else:
        api10 = openstack.FaultWrapper(auth.AuthMiddleware(
              limits.RateLimitingMiddleware(app)))

    mapper = urlmap.URLMap()
    mapper['/v1.0'] = api10
    mapper['/'] = openstack.FaultWrapper(reddwarf.api.versions.Controller())
    return mapper
