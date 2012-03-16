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
if len(argv) < 3:
    print "swupload.py <bucket> <file>"
    sys.exit(1)

try:
    swift.st_upload(opts, argv[1], argv[2])

except (swift.ClientException, HTTPException, socket.error), err:
    print str(err)
