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
    print "Usage: swdelete_con.py <container>"
    sys.exit(1)

try:
    print "delete container %s" % argv[1]
    items = swift.st_delete_container(opts, argv[1])

except (swift.ClientException, HTTPException, socket.error), err:
    error_queue.put(str(err))
