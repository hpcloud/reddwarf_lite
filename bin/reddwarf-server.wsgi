#!/usr/bin/env python
# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2011 OpenStack LLC.
# All Rights Reserved.
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

import gettext
import optparse
import os
import threading
import site
import sys

rdl_path = '/home/ubuntu/reddwarf_lite'

vepath = rdl_path + "/.venv/lib/python2.7/site-packages"
os.environ['PYTHON_EGG_CACHE'] = vepath

prev_sys_path = list(sys.path)
site.addsitedir(vepath)

new_sys_path = [p for p in sys.path if p not in prev_sys_path]

for item in new_sys_path:
    sys.path.remove(item)
    sys.path[:0] = new_sys_path

from reddwarf.common import service

gettext.install('reddwarf', unicode=1)

# If ../reddwarf/__init__.py exists, add ../ to Python search path, so that
# it will override what happens to be installed in /usr/(local/)lib/python...
possible_topdir = os.path.normpath(os.path.join(os.path.abspath(sys.argv[0]),
    os.pardir,
    os.pardir))
if os.path.exists(os.path.join(possible_topdir, 'reddwarf', '__init__.py')):
    sys.path.insert(0, possible_topdir)

from reddwarf import version
from reddwarf.common import config
from reddwarf.common import wsgi
from reddwarf.db import db_api
from paste import deploy

def create_options(parser):
    """Sets up the CLI and config-file options

    :param parser: The option parser
    :returns: None

    """
    parser.add_option('-p', '--port', dest="port", metavar="PORT",
        type=int, default=8779,
        help="Port the Reddwarf API host listens on. "
             "Default: %default")
    config.add_common_options(parser)
    config.add_log_options(parser)


os.chdir(rdl_path + "/bin")
oparser = optparse.OptionParser(version="%%prog %s"
    % version.version_string())
create_options(oparser)
(options, args) = config.parse_options(oparser)

try:
    print "Starting reddwarf-server"
    conf, app = config.Config.load_paste_app('reddwarf', options, args)
    db_api.configure_db(conf)                                                                                                                                                          

    newrelic_enabled = config.Config.get('newrelic_enabled', False)
    if newrelic_enabled == True or newrelic_enabled == 'True':
        import newrelic.agent
        newrelic.agent.initialize(os.path.join(rdl_path,"newrelic.ini"))
        print "NewRelic agent initialized"
        application = newrelic.agent.wsgi_application()(app)
    else:
        print "starting app without newrelic"
        application = app
except RuntimeError as error:
    import traceback
    print traceback.format_exc()
    sys.exit("ERROR: %s" % error)

