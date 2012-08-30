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

def wrap (message=None, detail=None):
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
    REDDWARF_CREATE = "There was a problem creating the requested DBaaS instance."
    IP_ASSIGN = "There was a problem assigning an IP address to the requested instance."
    RESTART = "There was a problem restarting the specified instance."
    INSTANCE_NOT_RUNNING = "The requested instance is not in running state."
    INSTANCE_LOCKED = "The requested instance has a blocking operation in progress at this moment. Try again later."
    MALFORMED_BODY = "The request body is malformed or missing required information."
    #QUOTA_EXCEEDED = "Creation of this instance would exceed the available resources of this account."
    QUOTA_EXCEEDED = "Quota has been reached for instance creation on this account."
    RAM_QUOTA_EXCEEDED = "Compute RAM Quota has been reached for this account."
    VOLUME_QUOTA_EXCEEDED = "Volume Space Quota has been reached for this account."
    
class Snapshot():
    NOT_FOUND = "The requested snapshot does not exist."
    DELETE = "There was a problem deleting the specified snapshot."
    CREATE = "There was a problem creating the requested snapshot."
    SWIFT_DELETE = "There was a problem deleting the specified snapshot."
    QUOTA_EXCEEDED = "Quota has been reached for snapshot creation on this account."
    NO_BODY_INSTANCE_ID = "The request body must contain an instanceId key."
    NO_BODY_NAME = "The request body must contain a name key."    

class Input():
    NONALLOWED_CHARACTERS_ID = "The id value contains non-allowed characters.  Only alphanumeric characters are allowed." 
    NONALLOWED_CHARACTERS_SNAPSHOT_ID = "The snapshotId value contains non-allowed characters.  Only alphanumeric characters are allowed."
    NONALLOWED_CHARACTERS_INSTANCE_ID = "The instanceId value contains non-allowed characters.  Only alphanumeric characters are allowed."    
    NONINTEGER_VOLUME_SIZE = "The volume size must be an integer value."