# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 HP Software, LLC
# All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from reddwarf.database import models

def get_instance(id):
    instance = models.DBInstance().find_by(id=id)
    return instance

def get_instance_by_hostname(hostname):
    instance = models.DBInstance().find_by(remote_hostname=hostname)
    return instance        

def get_snapshot(id):
    snapshot = models.Snapshot().find_by(id=id)
    return snapshot    

def update_guest_status(instance_id, state):
    guest = models.GuestStatus().find_by(instance_id=instance_id)
    # TODO: Handle situation where no matching record is found (e.g. if
    # a write to GuestStatus fails during create() for some reason)
    return guest.update(state=state)

def update_instance_with_ip(instance_id, public_ip):
    # public_ip might be public_ip or floating_ip
    instance = models.DBInstance().find_by(id=instance_id)
    # TODO: Handle situation where no matching record is found (e.g. if
    # a write to GuestStatus fails during create() for some reason)
    return instance.update(address=public_ip)

