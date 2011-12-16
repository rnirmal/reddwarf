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

"""
SQLAlchemy models for the reddwarf datastore
"""

from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.ext.declarative import declarative_base

from nova.db.sqlalchemy.models import NovaBase

import datetime


BASE = declarative_base()


class GuestStatus(BASE, NovaBase):
    """Represents the status of the guest or the service running within
       the guest"""
    __tablename__ = 'guest_status'

    instance_id = Column(Integer, primary_key=True)
    state = Column(Integer)
    state_description = Column(String(255))


class RootEnabledHistory(BASE, NovaBase):
    """
    Represents the date and time root was enabled for the MySQL database on an
    instance.
    """
    __tablename__ = 'root_enabled_history'

    instance_id = Column(Integer, primary_key=True)
    user_id = Column(Integer)

    def __eq__(self, other):
        return all([
            self.created_at == other.created_at,
            self.instance_id == other.instance_id,
            self.user_id == other.user_id])

    def __str__(self):
        return '<RootEnabledHistory: instance_id=%s, root_enabled_at=%s, root_enabled_by=%s>' % (self.instance_id, self.created_at, self.user_id)


class Config(BASE, NovaBase):
    """Contains configuration data"""
    __tablename__ = 'config'

    key = Column(String(255), primary_key=True)
    value = Column(String(255))
    description = Column(String(255))


class RsDnsRecord(BASE, NovaBase):
    """
    A simple pairing between a DNS record ID and its name.
    """
    __tablename__ = 'rsdns_records'

    name = Column(String(length=255), primary_key=True)
    id = Column('id', String(length=64))
    