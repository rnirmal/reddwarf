# Copyright (c) 2010-2011 OpenStack, LLC.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.


"""
NOVA LAZY PROVISIONING AUTH MIDDLEWARE

This WSGI component allows keystone act as an identity service for nova by
lazy provisioning nova projects/users as authenticated by auth_token.

"""

from nova import auth
from nova import context
from nova import flags
from nova import utils
from nova import wsgi
import webob.dec
import webob.exc


FLAGS = flags.FLAGS


class KeystoneAuthShim(wsgi.Middleware):
    """Lazy provisioning nova project/users from keystone tenant/user"""

    def __init__(self, application, db_driver=None):
        if not db_driver:
            db_driver = FLAGS.db_driver
        self.db = utils.import_object(db_driver)
        self.auth = auth.manager.AuthManager()
        super(KeystoneAuthShim, self).__init__(application)

    @webob.dec.wsgify(RequestClass=wsgi.Request)
    def __call__(self, req):
        # find or create user
        try:
            user_id = req.headers['X_USER']
        except:
            return webob.exc.HTTPUnauthorized()
        try:
            user_ref = self.auth.get_user(user_id)
        except:
            user_ref = self.auth.create_user(user_id)

        project_id = req.headers['X_TENANT']
        # create a project for tenant
        try:
            self.auth.get_project(project_id)
        except:
            self.auth.create_project(project_id, user_id)
        # ensure user is a member of project
        if not self.auth.is_project_member(user_id, project_id):
            self.auth.add_to_project(user_id, project_id)

        # Get the auth token
        auth_token = req.headers.get('X_AUTH_TOKEN')

        # Build a context, including the auth_token...
        # TODO(rnirmal): Relying on nova admin-ness for now, might need to fix
        # this once we the keystone refactoring gets done
        ctx = context.RequestContext(user_id, project_id,
                                     is_admin=user_ref.is_admin(),
                                     auth_token=auth_token)

        req.environ['nova.context'] = ctx
        return self.application
