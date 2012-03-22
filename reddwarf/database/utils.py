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

#from reddwarf.database import service
from reddwarf.database import models
from reddwarf.database import views

def get_instance(id):
    instance = models.DBInstance().find_by(id=id)
    instance = views.DBInstanceView(instance).show()
    return instance

def get_instance_by_hostname(hostname):
    instance = models.DBInstance().find_by(remote_hostname=hostname)
    instance = views.DBInstanceView(instance).show()
    return instance        

def get_snapshot(id):
    snapshot = models.Snapshot().find_by(id=id)
    snapshot = views.SnapshotView(instance).show()
    return instance    

def update_guest_status(instance_id, state, description=None):
    if not description:
        description = result_state.name(state)
        
    guest = models.GuestStatus().find_by(instance_id=instance_id)
    guest.update({'state': state,
                  'state_description': description})