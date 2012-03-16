#!/usr/bin/env python

import sys
import swift
from os import environ
import socket


try:
    from eventlet.green.httplib import HTTPException, HTTPSConnection
except ImportError:
    from httplib import HTTPException, HTTPSConnection

opts = {    'auth' : environ.get('ST_AUTH'),
            'user' : environ.get('ST_USER'),
            'key' : environ.get('ST_KEY'),
            'snet' : False,
            'prefix' : '',
            'auth_version' : '1.0'}
argv = sys.argv

if len(argv) < 2:
    print "Usage: swget_con.py <container>"
    sys.exit(1)

try:
    print "get container %s" % argv[1]
    objects = swift.st_get_container(opts, argv[1])

except (swift.ClientException, HTTPException, socket.error), err:
    print str(err)

if len(objects) == 0:
    print "container %s does not exist" % argv[1]
print objects

