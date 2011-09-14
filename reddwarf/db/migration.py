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
import sys

from migrate.versioning import api as versioning_api

try:
    from migrate.versioning import exceptions as versioning_exceptions
except ImportError:
    try:
        # python-migration changed location of exceptions after 1.6.3
        # See LP Bug #717467
        from migrate import exceptions as versioning_exceptions
    except ImportError:
        sys.exit(_("python-migrate is not installed. Exiting."))


def db_sync(sql_connection):
    """
    Syncs the database to the latest version. If it is not under version control
    then it's first version controlled and upgraded to the latest version

    :param sql_connection: sql connection url
    """
    repo_path = _find_migrate_repo()
    version_control(sql_connection)
    versioning_api.upgrade(sql_connection, repo_path)
    return db_version(sql_connection)


def db_version(sql_connection):
    """
    Get the current version of the database. Throws a DatabaseNotControlledError
    if the database is not under version control

    :param sql_connection: sql connection url
    """
    repo_path = _find_migrate_repo()
    return versioning_api.db_version(sql_connection, repo_path)


def db_upgrade(sql_connection, version):
    """Upgrades the database to the specified version
    
    :param sql_connection: sql connection url
    :param version: upgrade to version
    """
    repo_path = _find_migrate_repo()
    try:
        versioning_api.upgrade(sql_connection, repo_path,
                               version=version)
        return db_version(sql_connection)
    except (ValueError, KeyError):
        raise  ValueError("Invalid version '%s'" % version)


def db_downgrade(sql_connection, version):
    """Downgrades the database to the specified version

    :param sql_connection: sql connection url
    :param version: downgrade to version
    """
    repo_path = _find_migrate_repo()
    try:
        versioning_api.downgrade(sql_connection, repo_path,
                                 version=version)
        return db_version(sql_connection)
    except (ValueError, KeyError):
        raise  ValueError("Invalid version '%s'" % version)


def version_control(sql_connection):
    """Setup version control if not already done"""
    try:
        db_version(sql_connection)
    except versioning_exceptions.DatabaseNotControlledError:
        versioning_api.version_control(sql_connection, _find_migrate_repo())


def _find_migrate_repo():
    """Get the path for the migrate repository"""
    path = os.path.join(os.path.abspath(os.path.dirname(__file__)),
                        'migrate_repo')
    assert os.path.exists(path)
    return path
