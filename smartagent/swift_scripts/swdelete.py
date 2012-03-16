#!/usr/bin/env python

import sys
import swift
from os import environ
import socket


argv = sys.argv
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

if len(argv) < 3:
    print "USAGE: swdelete.py <container> <object>"
    sys.exit(1)

try:
    print "delete object %s/%s" % (argv[1], argv[2])
    items = swift.st_delete(opts, argv[1], argv[2])

except (swift.ClientException, HTTPException, socket.error), err:
    error_queue.put(str(err))
