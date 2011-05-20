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

from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base

from nova.db.sqlalchemy.models import NovaBase


BASE = declarative_base()


class GuestStatus(BASE, NovaBase):
    """Represents the status of the guest or the service running within
       the guest"""
    __tablename__ = 'guest_status'

    instance_id = Column(Integer, primary_key=True)
    state = Column(Integer)
    state_description = Column(String(255))
