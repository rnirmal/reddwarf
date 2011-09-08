# Copyright 2010 OpenStack LLC.
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

from sqlalchemy import Column, Integer, MetaData, String, Table
#from nova import log as logging

meta = MetaData()

c_uuid = Column('uuid',
                String(length=64, convert_unicode=False, assert_unicode=None,
                unicode_error=None, _warn_on_bytestring=False),
                nullable = True)


def upgrade(migrate_engine):
    volumes_table = Table('volumes', meta, autoload=True,
                      autoload_with=migrate_engine)
    meta.bind = migrate_engine
    volumes_table.create_column(c_uuid)

def downgrade(migrate_engine):
    volumes_table = Table('volumes', meta, autoload=True,
                      autoload_with=migrate_engine)
    meta.bind = migrate_engine
    volumes_table.drop_column(c_uuid)
