#!/usr/bin/env python

import sys
import socket
import os
from nova import log as logging
from nova import test
sys.path.append('/home/nova/reddwarf/')
import swift



#LOG = logging.getLogger('reddwarf.tests.hpcs.hpcs_test')
#LOG.setLevel(logging.DEBUG)

"""Read environment variables for testing credentials  If you're using a mac, set these in your ~/.MacOSX/environment.plist file"""
authenticated = False

env = os.environ.copy()
AUTH_USERNAME = env.get("ST_USER","")
AUTH_PASSWORD = env.get("ST_PASSWORD","")
AUTH_PASSWORD = "hello"

AUTH_URL = "https://region-a.geo-1.identity.hpcloudsvc.com:35357/v2.0/tokens"


class HPCSTest(test.TestCase):
    def test_authenticate(self):
        """Test to authenticate a user"""
        print("Testing authentication")

        result = swift.get_auth(AUTH_URL, AUTH_USERNAME, AUTH_PASSWORD, False, "2.0")

        print dir(result)
