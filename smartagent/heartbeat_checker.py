import time
import subprocess
import string
import threading
import os
from result_state import ResultState
class HeartbeatChecker(threading.Thread):
    
    def __init__(self):
        self.alive = True
        threading.Thread.__init__(self)
        self.time_interval_in_seconds = 60*5 # heartbeat check per 5 minutes
    
    def _get_response_body_for_heartbeat_checker(self, status):
        return {"method": "", 
                  "args": {"timestamp": time.ctime(time.time()),
                            "hostname": os.uname()[1],
                            "ip": "",
                             "state": status 
                          }} 
    def lightweight_mysql_running_checker(self):
        proc = subprocess.Popen("sudo netstat -tap | grep mysql", shell=True, stdout=subprocess.PIPE)
        output = proc.stdout.read()
        proc.stdout.close()
        proc.wait()
        
        for line in output.split('\n'):
            cols = line.split(' ')
            for col in cols:
                if 'mysqld' in col and '/' in col:
#                    words = col.split('/')
                    #return words[0] # return process id of mysqld
                    return True
        return False

    def run(self):
        while self.alive:
            if self.lightweight_mysql_running_checker:
                self._get_response_body_for_heartbeat_checker(ResultState.RUNNING)
#                print self._get_response_body_for_heartbeat_checker("running")
            else :
                self._get_response_body_for_heartbeat_checker(ResultState.STOP)
#                print self._get_response_body_for_heartbeat_checker("stop")
            time.sleep(self.time_interval_in_seconds)

def main():
    heartbeat_checker = HeartbeatChecker()
    heartbeat_checker.start()
    heartbeat_checker.join()
    
if __name__ == '__main__':
    main()