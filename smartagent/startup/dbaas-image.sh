#!/bin/bash

# this version of the script does everything up to what the
# cloud init should do

# don't ask me no questions and I won't tell you no lies 
export DEBIAN_FRONTEND=noninteractive

# import PGP keys
gpg --keyserver  hkp://keys.gnupg.net --recv-keys 1C4CBDCDCD2EFD2A
gpg -a --export CD2EFD2A | apt-key add -

# set up the percona repo
echo "deb http://repo.percona.com/apt lucid main
deb-src http://repo.percona.com/apt lucid main" >/etc/apt/sources.list.d/percona.list

apt-get update
# lvm and xfs

# apparmor, garhr, remote it
dpkg -r apparmor
update-rc.d -f apparmor remove 

# easier to install everything all at once
apt-get --force-yes --yes install lvm2 xfsprogs xfsdump percona-server-common-5.5  percona-server-server-5.5 percona-server-test-5.5  percona-server-client-5.5 libmysqlclient18  libmysqlclient-dev xtrabackup percona-toolkit sysstat git python-pip python-swift swift policycoreutils python-mysqldb python-nova libdbd-mysql-perl libdbi-perl python-pip python-dev

# python pip installs
pip install --upgrade pika
pip install --upgrade amqplib
pip install --upgrade kombu 
pip install --upgrade mysql-python
pip install --upgrade swift
pip install --upgrade python-daemon
easy_install pika

# have to answer 'y' to turning on cron script
dpkg-reconfigure sysstat

# remove last line in /etc/fstab which has the old mount point that
# cloudinit automatically adds for /mnt and /dev/vdb
sed -i '$d' /etc/fstab

# change root/admin password
/usr/bin/mysqladmin -u root password hpcs 
# create agent DB account
# TODO: get privileges set up so agent can't read user, vice versa
/usr/bin/mysql -u root -phpcs -e "grant all privileges on *.* to 'os_admin'@'localhost' identified by 'hpcs' with grant option;"
# create user account. TODO: this will be passed via the API
/usr/bin/mysql -u root -phpcs -e "grant all privileges on *.* to 'dbas'@'%' identified by 'hpcs' with grant option;"

# now shut down because we have changed the innodb log file size
# and when we restart, it would otherwise report and error
/etc/init.d/mysql stop

# remove innodb log file since log file size is changed
rm /var/lib/mysql/ib_logfile*

# copy stock my.cnf
cp /home/nova/reddwarf/startup/my.cnf/xsmall /etc/mysql/my.cnf

echo "[client]
# this is a VERY stock my.cnf. I know, it needs to be tuned.
user=os_admin
password=hpcs
" > /home/nova/.my.cnf

ln -s /home/nova/.my.cnf /root/.my.cnf

# start
/etc/init.d/mysql start

# create, set up nova user
useradd -d /home/nova -g mysql -m -s /bin/bash -p n0va nova
mkdir /home/nova/logs
mkdir /home/nova/lock
mkdir /home/nova/backup_logs

cd /home/nova
# clone git. The cloud init script will do a pull
sudo git clone https://github.com/hpcloud/reddwarf.git

# HACK ALERT! FIX THIS!
ln -s /home/nova/reddwarf/swiftapi/swift.py /home/nova/reddwarf/smartagent/swift.py

# HACK ALERT! FIX THIS! This should be a proper shell script that calls the python
ln -s /home/nova/reddwarf/smartagent/smartagent_launcher.py /etc/init.d/smartagent 
#cp /home/nova/reddwarf/smartagent/startup/smartagent /etc/init.d

# make sure nova owns
chown nova:mysql -R /home/nova/

# Percona MySQL upstart script
cp /home/nova/reddwarf/smartagent/startup/mysql.conf /etc/init
# remove the init script since using upstart
update-rc.d -f mysql remove
rm /etc/init.d/mysql

# this needs to be in place for nova user to be able to do things like
# restart MySQL
cp /home/nova/reddwarf/smartagent/startup/sudoers /etc

# set init script runlevels
update-rc.d smartagent defaults 90

# make xtrabackup backup location directory
mkdir /var/lib/mysql-backup
# make sure to set perms
chown nova:mysql /var/lib/mysql-backup

echo "export PYTHONPATH=/home/nova/reddwarf/swiftapi" >> /home/nova/.bashrc
echo "export PYTHONPATH=/home/nova/reddwarf/swiftapi" >> /root/.bashrc

# stop, because we want to make an image
/etc/init.d/mysql stop

# clear out log
rm /var/log/mysql/*.err

# NOW YOU CAN IMAGE THE INSTANCE
