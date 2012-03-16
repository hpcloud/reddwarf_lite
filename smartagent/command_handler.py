#!/usr/bin/python

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
import sys
import paths
import _mysql
from smartagent_persistence import DatabaseManager
import logging
import random
from result_state import ResultState
import os
import time
import subprocess
import tarfile
try:
    import swift
except Exception:
    pass
import socket
import string 
from check_mysql_status import MySqlChecker
try:
    from eventlet.green.httplib import HTTPException, HTTPSConnection
except ImportError:
    from httplib import HTTPException, HTTPSConnection


def random_string(size=6):  # TODO: move to utils.py
    """ Generate a random string to be used for password """
    # string to use
    chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    # join random chars of size N and return
    return ''.join(random.choice(chars) for x in range(size))


class MysqlCommandHandler:
    """ Class for passing commands to mysql """
    
    # TODO: extract to paths.py
    def __init__(self,
                 host_name='localhost',
                 database_name='mysql',
                 config_file=os.path.join(paths.mycnf_base, '.my.cnf'),
                 logger=logging.getLogger(paths.smartagent_name)):
        self.logger = logger
        self.persistence_agent = DatabaseManager(
            host_name=host_name,
            database_name=database_name,
            config_file=config_file,
            logger=self.logger)
        self.persistence_agent.open_connection()
        self.checker = MySqlChecker()

        if not os.path.exists(paths.backlog_path):
             try:
                 os.makedirs(paths.backlog_path)
             except OSError as os_error:
                 self.logger.debug("OS error while creating %s: %s",
                     paths.backlog_path,
                     os_error)

    def create_user(self,
                    username,
                    host='localhost',
                    newpassword=random_string()):
        # create a new user
        sql_commands = [
            "grant all privileges on *.* to '%s'@'%s' identified by '%s'"
            % (username, host, newpassword)]
        if self.persistence_agent.execute_sql_commands(sql_commands):
            return ResultState.SUCCESS
        else:
            self.logger.error("Create user %s failed",username)
            return ResultState.FAILED

    def delete_user(self, username):
        """
        Delete database user, all grants
        """
        sql_commands = []
        sql_delete = \
            "delete from mysql.user where User = '%s'" % username
        sql_flush = "FLUSH PRIVILEGES"
        sql_commands.append(sql_delete)
        sql_commands.append(sql_flush)
        if self.persistence_agent.execute_sql_commands(sql_commands):
            return ResultState.SUCCESS
        else:
            self.logger.error("Delete user '%s' failed", username)
            return ResultState.FAILED

    def delete_user_host(self, username, host):
        """
        Delete the user, specific user@host grant
        """
        sql_commands = [
            "drop user '%s'@'%s'" % (username, host)]
        if self.persistence_agent.execute_sql_commands(sql_commands):
            return ResultState.SUCCESS
        else:
            self.logger.error("Uelete user '%s'@'%s' failed", username, host)
            return ResultState.FAILED

    # TODO: user password, not the root user - make sure to not change root user password
    def reset_user_password(self,
                            username='dbas',
                            newpassword='something'):
        """
        Reset the user's password
        """
        sql_update = \
            "update mysql.user set Password=PASSWORD('%s') WHERE User='%s'"\
            % (newpassword, username)
        sql_flush = "FLUSH PRIVILEGES"
        sql_commands = [sql_update, sql_flush]
        if self.persistence_agent.execute_sql_commands(sql_commands):
            return ResultState.SUCCESS
        else:
            self.logger.error("Reset password for %s failed", username)
            return ResultState.FAILED

    def reset_agent_password(self, username='os_admin'):
        """
        Reset the MySQL account password for the agent's account
        """
        newpassword = random_string(16)
        sql_commands = ["SET PASSWORD FOR '%s'@'localhost'"\
                        " PASSWORD('%s')" % (username, newpassword)]
        if self.persistence_agent.execute_sql_commands(sql_commands):
            try:
                write_dotmycnf(username, newpassword)
                return ResultState.SUCCESS
            except OSError as error:
                self.logger.error("Agent password reset; error writing .cnf file: %s", error)
        else:
            self.logger.error("Reset agent password failed")
        return ResultState.FAILED

    def create_database(self, database_name):
        """
        Create a database
        """
        assert(database_name)
        sql_commands = [ "create database `%s`" % database_name ]
        if self.persistence_agent.execute_sql_commands(sql_commands):
            return ResultState.SUCCESS
        else:
            self.logger.error("Create database %s failed", database_name)
            return ResultState.FAILED

    def drop_database(self, database_name):
        """
        Drop a database
        """
        assert(database_name)
        sql_commands = [ "drop database `%s`" % database_name ]
        if self.persistence_agent.execute_sql_commands(sql_commands):
            return ResultState.SUCCESS
        else:
            self.logger.error("Drop database %s failed", database_name)
            return ResultState.FAILED

    def _get_snapshot_size(self, path):
        return os.path.getsize(path)
    
    def _get_response_body_for_create_snapshot(self,
                                              container,
                                              path_specifier,
                                              result,
                                              snapshot_size=0):
        #temp = 'mysql-backup' + '/' + path_specifier + '.tar.gz'
        if result == ResultState.SUCCESS:
            temp_file_name = '%s%s' % (os.path.join(container, path_specifier), '.tar.gz')
        else:
            temp_file_name = 'N/A'
        
        return {"method": "update_snapshot_state", 
                "args": {"sid": path_specifier, 
                         "state": result, 
                         "storage_uri": temp_file_name,
                         "storage_size": snapshot_size }}

    def get_leading_path(self, path):
        #print path
        directs = path.split('/')
        #print directs
        leading_path =''
        for direct in directs:
            leading_path = os.path.join(leading_path, direct)
        
        #print '%s/' % leading_path
        return '%s/' % leading_path
    
    def create_tar_file(self, path, tar_name):
        try:
            target_name = '%s%s' % (tar_name, '.tar.gz')
            leading_path = self.get_leading_path(path)
            self.logger.debug('the leading path for tar file is %s', leading_path)
            with tarfile.open(target_name, 'w:gz') as tar:
                for (path, dirs, files) in os.walk(path):
                    for file in files:
                        filename = os.path.join(path, file)
                        final_member_name = filename.replace(leading_path, '')
                        #self.logger.debug('final_member_name: %S', final_member_name)
                        #tar.add(name=filename, recursive=False)
                        tar.add(name=filename, arcname=final_member_name)
            return target_name
        except Exception as tarfile_exception:
            self.logger.error('tar/compress snapshot failed somehow: %s',
                tarfile_exception)
            return ResultState.FAILED  
    
    def keyword_checker(self, keyword_to_check, log_path):
        try:
            with open(log_path, "r") as f:
                last_lines = f.readlines()[-1:]
        
            for line in last_lines:
                if keyword_to_check in line:
                    self.logger.debug("innobackupex runs successfully; read: %s",
                        line)
                    return ResultState.SUCCESS
                else:
                    self.logger.error("innobackupex run failed; read: %s ",
                        line)
                    return ResultState.FAILED
        except Exception:
            self.logger.error("log file does not exist: %s", log_path)
            
            
    def check_process(self, proc):
        status = proc.poll()
        iteration = 0
        TIME_OUT = 8640 # time out after 12 hours = 60 * 60 * 12 / 5
        
        while status !=0 and iteration < TIME_OUT:
            iteration = iteration + 1
            if status is None:
                self.logger.debug('subprocess is still alive; iteration: %d', iteration)
                time.sleep(5)
                status = proc.poll()
            else:
                self.logger.error('subprocess encounter errors, exit code: %s' % status)
                return 'error'
        if iteration == TIME_OUT:
            return 'timed out'
        else:
            return 'normal'
    
    def create_db_snapshot(self, path_specifier, st_user, st_key, st_auth, container='mysql-backup-dbasdemo'):
        path = os.path.join(paths.backup_path, path_specifier)
        log_home = os.path.join(paths.backlog_path, path_specifier)
        keyword_to_check = "innobackupex: completed OK!"  # TODO: replace with regexp?
        # create backup snapshot first
        
        log_path = '%s%s' % (log_home, '_innobackupex_create.log')
        inno_backup_cmd = "innobackupex --no-timestamp %s > %s 2>&1" % (path, log_path)

        try:
            proc = subprocess.Popen(inno_backup_cmd, shell=True)
        except (OSError, ValueError) as ex_oserror:
            self.logger.error('popen exception caught for create db backup: %s', ex_oserror)
        except Exception as ex:
            self.logger.error('popen exception caught for create db backup: %s', ex)
        else:
            if self.check_process(proc) != 'normal':
                self.logger.error('snapshot subprocess failed: %s',
                    str(sys.exc_info()[0]))
                return self._get_response_body_for_create_snapshot(container,
                    path_specifier,
                    ResultState.FAILED)
        
        result = self.keyword_checker(keyword_to_check, log_path)
        if result != ResultState.SUCCESS:
            self.logger.error('snapshot is not ready for preparation')
            return self._get_response_body_for_create_snapshot(container,
                path_specifier,
                ResultState.FAILED)

        # prepare the snapshot for uploading to swift
        
        log_path = '%s%s' % (log_home, '_innobackupex_prepare.log')
            
        inno_prepare_cmd = "innobackupex --use-memory=1G --apply-log %s > %s 2>&1" % (path, log_path)

        try:
            proc = subprocess.Popen(inno_prepare_cmd, shell=True)
        except (OSError, ValueError) as ex_oserror:
            self.logger.error('popen exception caught for prepare db snapshot: %s', ex_oserror)
        except Exception as ex:
            self.logger.error('popen exception caught for prepare db snapshot: %s', ex)
        else:
            if self.check_process(proc) != 'normal':
                self.logger.error('preparation failed somehow')
                return self._get_response_body_for_create_snapshot(container,
                    path_specifier,
                    ResultState.FAILED)
            
        result = self.keyword_checker(keyword_to_check, log_path)
        if result != ResultState.SUCCESS:
            self.logger.error('preparation encounter exceptions or errors')
            return self._get_response_body_for_create_snapshot(container,
                path_specifier,
                ResultState.FAILED)
        
        # tar the entire backup folder
        try:
            tar_result = self.create_tar_file(path, path_specifier)
            self.logger.debug('tar result: %s', tar_result)
            if tar_result == ResultState.FAILED:
                return self._get_response_body_for_create_snapshot(container,
                    path_specifier,
                    ResultState.FAILED,
                    self._get_snapshot_size(tar_result))

            # start upload to swift
            opts = {'auth' : st_auth,
                    'user' : st_user,
                    'key' : st_key,
                    'snet' : False,
                    'prefix' : '',
                    'auth_version' : '1.0'}

            try:
                cont = swift.st_get_container(opts, container)
                if not len(cont):
                    # create container
                    swift.st_create_container(opts, container)
                swift.st_upload(opts, container, tar_result)
            except (swift.ClientException, HTTPException, socket.error), err:
#            except (HTTPException, socket.error), err:
                self.logger.error('Failed to upload snapshot to swift: %s', err)
                return self._get_response_body_for_create_snapshot(container,
                    path_specifier,
                    ResultState.FAILED,
                    self._get_snapshot_size(tar_result))
            else:
                response_body = self._get_response_body_for_create_snapshot(container,
                    path_specifier,
                    ResultState.SUCCESS,
                    self._get_snapshot_size(tar_result))
        finally:  # create_tar_file
            # remove .tar.gz file after upload
            try:
                if os.path.isfile(tar_result):
                    os.remove(tar_result)
            except Exception as ex:
                self.logger.error('Exception removing .tar file: %s', ex)

        self.logger.debug(response_body)
        return response_body

    def is_mysql_running(self):
        return self.checker.check_if_running(sleep_time_seconds=2, number_of_checks=2)
    
    def restart_database(self):
        """ This restarts MySQL for reading conf changes"""
        try: 
            proc = subprocess.Popen("sudo service mysql restart", shell=True)
        except (OSError, ValueError) as ex_oserror:
            self.logger.error('Popen exception caught: %s', ex_oserror)
            return ResultState.FAILED
        except Exception as ex:
            self.logger.error('Popen exception caught: %s', ex)
            return ResultState.FAILED
        else:
            if self.check_process(proc) != 'normal':
                self.logger.error('restart mysql failed somehow')
                return ResultState.FAILED
            return self.is_mysql_running()

    def stop_database(self):
        """ This stop MySQL """
        print 'process reached here'
        try:
            proc = subprocess.Popen("sudo service mysql stop", shell=True)
            print proc
        except (OSError, ValueError) as ex_oserror:
            self.logger.error('Popen exception caught: %s', ex_oserror)
            return ResultState.FAILED
        except Exception as ex:
            self.logger.error('Popen exception caught: %s', ex)
            return ResultState.FAILED
        else:
            if self.check_process(proc) != 'normal':
                self.logger.error('restart mysql failed somehow')
                return ResultState.FAILED
            return not self.is_mysql_running()
        
    def start_database(self):
        """ This start MySQL """
        try:
            proc = subprocess.Popen("sudo service mysql start", shell=True)
        except (OSError, ValueError) as ex_oserror:
            self.logger.error('Popen exception caught: %s', ex_oserror)
            return ResultState.FAILED
        except Exception as ex:
            self.logger.error('Popen exception caught: %s', ex)
            return ResultState.FAILED
        else:
            if self.check_process(proc) != 'normal':
                self.logger.error('restart mysql failed somehow')
                return ResultState.FAILED
            return self.is_mysql_running()
        
    def get_response_body_for_apply_snapshot(self, result):
        
        return {"method": "update_instance_state", 
                "args": {"hostname": os.uname()[1], 
                         "state": result }}
        
    def extract_tar_file(self, dest_path, tar_name):
        try:
            with tarfile.open(tar_name, 'r:gz') as tar_file:
                tar_file.extractall(dest_path)
                return True
        except Exception as tarfile_exception:
            self.logger.error('untar/decompress snapshot failed somehow: %s',
                tarfile_exception)
            return False
    
    def apply_db_snapshot(self, uri, st_user, st_key, st_auth):
        
        self.logger.debug('inside apply_db_snapshot, we are here')
        # stop mysql server
        if not self.stop_database():
            return self.get_response_body_for_apply_snapshot(ResultState.FAILED)
        
        # push the current data to history folder and set the correct permission
        try:
            time_stamp = time.time()
            os.system('sudo mv /var/lib/mysql /var/lib/mysql.%s' % time_stamp)
            self.logger.debug('after sudo mv')
            os.system('sudo mkdir /var/lib/mysql')
            self.logger.debug('after sudo mkdir')
            os.system('sudo chown -R mysql:mysql /var/lib/mysql')
            self.logger.debug('after sudo chown -R')
            os.system('sudo chmod 775 /var/lib/mysql')
            self.logger.debug('after sudo chmod')
        except os.error as os_error:
            self.logger.error('remove historical data encounter errors: %s', os_error)
        except Exception as ex:
            self.logger.error('remove historical data encounter generic errors: %s', ex)
            
        # parse the uri to get the swift container and object
        paras = string.split(uri, '/')
        container_name = paras[0]
        snapshot_name = paras[1]
        self.logger.debug('passed in swift container: %s and snapshot name: %s', container_name, snapshot_name)
        
        
        # download snapshot from swift
        opts = {'auth' : st_auth,
                    'user' : st_user,
                    'key' : st_key,
                    'snet' : False,
                    'prefix' : '',
                    'auth_version' : '1.0'}
            
        try:
            cont = swift.st_get_container(opts, container_name)
            if not len(cont):
                self.logger.error('target swift container is empty')
                result = self.get_response_body_for_apply_snapshot(ResultState.FAILED)
                self.logger.debug('return message body: %s', result)
                return result
            swift.st_download(opts, container_name, snapshot_name)
            
        except (swift.ClientException, HTTPException, socket.error), err:
            self.logger.error('Failed to download snapshot from swift: %s', err)
            result = self.get_response_body_for_apply_snapshot(ResultState.FAILED)
            self.logger.debug('return message body: %s', result)
            return result
        
        # decompress snapshot
        if not self.extract_tar_file('/var/lib/mysql', snapshot_name):
            return self.get_response_body_for_apply_snapshot(ResultState.FAILED)

        # reset the permission for mysql datadir again and remove .tar.gz file
        try:
            os.system('sudo chown -R mysql:mysql /var/lib/mysql')
            self.logger.debug('after sudo chown on mysql datadir')
            os.system('sudo rm %s' % snapshot_name)
            self.logger.debug('after sudo rm the tar.gz file')
        except os.error as os_error:
            self.logger.error('reset permission (before restart mysql) encounter errors: %s', os_error)
        except Exception as ex:
            self.logger.error('reset permission (before restart mysql) encounter generic errors: %s', ex)
            
        # restart mysql
        if not self.start_database():
            return self.get_response_body_for_apply_snapshot(ResultState.FAILED)
        
        return self.get_response_body_for_apply_snapshot(ResultState.RUNNING)

    def write_dotmycnf(self, user='os_admin', password='hpcs'):
        """
        Write the .my.cnf file so as the user does not require credentials
        for the DB """
        cnf_file_name = os.path.join(paths.mycnf_base, paths.mysql_config_file)
        with open (cnf_file_name, 'w') as mycf:
            mycf.write( "[client]\nuser={}\npassword={}" . format(user, password))


def main():
    """ main program """
    handler = MysqlCommandHandler()
#    handler.reset_user_password(this_variable_should_be_username_of_tenant, 'hpcs')
    #handler.create_db_snapshot(container='mysql-backup-dbasdemo', path_specifier='anna')
    #handler.restart_database()
    handler.apply_db_snapshot('mysql-backup-dbasdemo/anna.tar.gz', 'st_user', 'st_key', 'st_auth')
    
if __name__ == '__main__':
    main()
