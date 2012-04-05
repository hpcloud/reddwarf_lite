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


class ResultState:
    """States of operation result"""
    SUCCESS = 0x00
    RUNNING = 0x01
    NOSTATE = 0x02
    FAILED = 0x03
    STOP = 0x04
    RESTARTING = 0x05

    _STATE_MAP = {
        SUCCESS: 'success',
        RUNNING: 'running',
        NOSTATE: 'pending',
        FAILED: 'failed',
        STOP: 'stop',
        RESTARTING: 'restarting',
    }

    @staticmethod
    def name(code):
        return ResultState._STATE_MAP[code]

    @staticmethod
    def valid_states():
        return ResultState._STATE_MAP.keys()