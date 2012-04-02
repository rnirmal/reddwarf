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

from sqlalchemy import Column
from sqlalchemy import MetaData
from sqlalchemy import String
from sqlalchemy import Table

from migrate.changeset import alter_column

meta = MetaData()

old_c_value = Column('value', String(length=255, convert_unicode=False,
                                 assert_unicode=None, unicode_error=None,
                                 _warn_on_bytestring=False))
new_c_value = Column('value', String(length=5000, convert_unicode=False,
                                 assert_unicode=None, unicode_error=None,
                                 _warn_on_bytestring=False))


def upgrade(migrate_engine):
    instance_metadata = Table('instance_metadata', meta, autoload=True,
                              autoload_with=migrate_engine)
    meta.bind = migrate_engine
    alter_column(new_c_value, table=instance_metadata)

def downgrade(migrate_engine):
    instance_metadata = Table('instance_metadata', meta, autoload=True,
                              autoload_with=migrate_engine)
    meta.bind = migrate_engine
    alter_column(old_c_value, table=instance_metadata)
