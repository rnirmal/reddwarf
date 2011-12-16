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

from sqlalchemy import *
from migrate import *


meta = MetaData()


dns_records = Table('rsdns_records', meta,
               Column('created_at', DateTime(timezone=False)),
               Column('updated_at', DateTime(timezone=False)),
               Column('deleted_at', DateTime(timezone=False)),
               Column('deleted', Boolean(create_constraint=True, name=None)),
               Column('name', String(length=255), primary_key=True),
               Column('id', String(length=64)))


def upgrade(migrate_engine):
    meta.bind = migrate_engine
    dns_records.create()

def downgrade(migrate_engine):
    meta.bind = migrate_engine
    dns_records.drop()
