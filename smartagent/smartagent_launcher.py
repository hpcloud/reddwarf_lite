#!/usr/bin/env python

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
import os
import signal
import daemon
import lockfile
import sys
import time
import paths
import service

__author__ = 'dragosmanolescu'
__email__ = 'dragosm@hp.com'
__python_version__ = '2.7.2'

PID_FILENAME = os.path.join(paths.smartagent_working_dir, paths.smartagent_pid_file_name)

def main():
    """Activates the smart agent by instantiating an instance of SmartAgent
       and then calling its start_consuming() method."""


    if len(sys.argv) == 2:
        if 'start' == sys.argv[1]:
            start()
        elif 'stop' == sys.argv[1]:
            stop()
        elif 'restart' == sys.argv[1]:
            restart()
        elif 'status' == sys.argv[1]:
            status()
        else:
            print "unknown command"
            sys.exit(2)
        sys.exit(0)
    else:
        print "Usage: %s start|stop|restart|status" % sys.argv[0]
        sys.exit(2)

def start():
    pid = _get_daemon_pid()
    if pid:
        if _is_process_running(pid):
            print 'smartagent daemon already running'
            sys.exit(os.EX_USAGE)
        else:
            # stale PID file
            os.remove(PID_FILENAME)
    smart_agent_service = service.Service(paths.smartagent_working_dir)
    context = daemon.DaemonContext(
        working_directory=paths.smartagent_working_dir,
        pidfile=lockfile.FileLock(str(os.path.join(paths.smartagent_working_dir,
            'smartagent_launcher'))))
    context.signal_map = {
        signal.SIGTERM: smart_agent_service.shutdown,
        signal.SIGHUP: smart_agent_service.shutdown,
        signal.SIGUSR1: smart_agent_service.shutdown
        }
    smart_agent_service.setup()
    print "Starting %s" % paths.smartagent_name
    try:
        with context:  # daemonize
            smart_agent_service.start()
            # launcher process ends here
    except lockfile.Error as le:
        print('LockError: %s' % le)

def _get_daemon_pid():
    if not os.path.isfile(PID_FILENAME):
        return None
    with open(PID_FILENAME, 'r') as pid_file:
        pid_string = pid_file.read().strip()
    try:
        pid = int(pid_string)
    except ValueError:
        return None
    return pid

def _is_process_running(pid):
    try:
        os.kill(pid,0)
    except OSError as os_error:
        return False
    else:
        return True

def stop(shouldExit=True):
    print "Stopping %s" % paths.smartagent_name
    pid = _get_daemon_pid()
    if pid:
        if _is_process_running(pid):
            # process running
            try:
                for i in range(1,10):
                    # sending HUP rather than TERM to get around AppArmor
                    os.kill(pid, signal.SIGHUP)
                    time.sleep(1)
                print "Launcher can't kill daemon (PID %d)" % pid
                if shouldExit:
                    sys.exit(os.EX_OSERR)
            except OSError as os_error:
                pass
        else:
            # stale PID file
            os.remove(PID_FILENAME)
    else:
        print "No/invalid PID file"
        if shouldExit:
            sys.exit(os.EX_OSFILE)


def restart():
    stop(shouldExit=False)
    start()

def status():
    print "%s status: " % paths.smartagent_name,
    pid = _get_daemon_pid()
    if not pid:
        print "not running"
    else:
        try:
            os.kill(pid, 0)
        except OSError as os_error:
            print "running but process %d non responsive" % pid
            sys.exit(os.EX_OSERR)
        print "running, PID=%d" % pid

if __name__ == '__main__':
    main()

