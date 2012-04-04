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

def wrap (message=None, detail="none"):
    error = {'error':
                {
                 'message': message, 
                 'detail': detail, 
                 } 
            }
    return error

class Instance():
    NOT_FOUND = "The requested instance does not exist."
    NOT_FOUND_NOVA = "The Nova instance pointed to by this instance does not exist."
    NOVA_DELETE = "There was a problem deleting the specified Nova instance."
    REDDWARF_DELETE = "There was a problem deleting the specified DBaaS instance."
    GUEST_DELETE = "There was a problem deleting the guest record associated with this instance."
    RESET_PASSWORD = "There was a problem resetting the password on the specified instance."
    NOVA_CREATE = "There was a problem creating the requested Nova instance."
    REDDWARF_CREATE = "There was a problem creating the requested DBaaS instance."
    GUEST_CREATE = "There was a problem creating the guest record associated with this instance."
    IP_ASSIGN = "There was a problem assigning an IP address to the requested instance."
    RESTART = "There was a problem restarting the specified instance."
    INSTANCE_NOT_RUNNING = "The requested instance is not in running state."
    INSTANCE_LOCKED = "The requested instance is temporarily locked due to operation in progress."
    
class Snapshot():
    NOT_FOUND = "The requested snapshot does not exist."
    DELETE = "There was a problem deleting the specified snapshot."
    CREATE = "There was a problem creating the requested snapshot."
    SWIFT_DELETE = "There was a problem deleting the specified snapshot."