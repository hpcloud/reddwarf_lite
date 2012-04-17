import unittest
import os
from reddwarf.database.utils import create_boot_config
import ConfigParser
import tempfile

__author__ = 'dragosmanolescu'

class BootConfigurationTest(unittest.TestCase):

    def test_boot_configuration_creation_no_swift(self):
        cm = { "rabbit_host" : "rabbit.host",
               "rabbit_port" : "1234",
               "rabbit_use_ssl" : "True",
               "rabbit_userid" : "ruser",
               "rabbit_password" : "rpassword",
               "rabbit_virtual_host" : "vhost"}
        credential = { 'tenant_id' : "jeff@amzon.com",
                       'user_name' : "bzos@amzon.com",
                       'password' : "123456ABCDEF" }
        config = create_boot_config(cm, credential, None, "dbpassword")
        try:
            with tempfile.NamedTemporaryFile(delete=False) as tf:
                tf.write(config)
                file_name = tf.name
            config = ConfigParser.SafeConfigParser()
            config.read(file_name)
            self.assertTrue(config.has_section("messaging"))
            self.assertEqual(cm["rabbit_host"], config.get("messaging", "rabbit_host"))
            self.assertEqual(cm["rabbit_port"], config.get("messaging", "rabbit_port"))
            self.assertEqual(cm["rabbit_use_ssl"], config.get("messaging", "rabbit_use_ssl"))
            self.assertEqual(cm["rabbit_userid"], config.get("messaging", "rabbit_userid"))
            self.assertEqual(cm["rabbit_password"], config.get("messaging", "rabbit_password"))
            self.assertEqual(cm["rabbit_virtual_host"], config.get("messaging", "rabbit_virtual_host"))
            self.assertTrue(config.has_section("database"))
            self.assertEqual("dbpassword", config.get("database", "initial_password"))
            self.assertFalse(config.has_section("snapshot"))
            os.remove(file_name)
        except Exception, e:
            print "EXCEPTION", e
            self.assertTrue(False)

    def test_boot_configuration_creation_with_swift(self):
        cm = { "rabbit_host" : "rabbit.host",
               "rabbit_port" : "1234",
               "rabbit_use_ssl" : "True",
               "rabbit_userid" : "ruser",
               "rabbit_password" : "rpassword",
               "rabbit_virtual_host" : "vhost",
               "reddwarf_proxy_swift_auth_url" : "http://127.0.0.1:5000/v2.0"
               }
        credential = { 'tenant_id' : "jeff@amzon.com",
                       'user_name' : "bzos@amzon.com",
                       'password' : "123456ABCDEF" }
        config = create_boot_config(cm, credential, "the-storage-uri", "dbpassword")
        try:
            with tempfile.NamedTemporaryFile(delete=False) as tf:
                tf.write(config)
                file_name = tf.name
            config = ConfigParser.SafeConfigParser()
            config.read(file_name)
            self.assertTrue(config.has_section("snapshot"))
            self.assertEqual("the-storage-uri", config.get("snapshot", "snapshot_uri"))
            self.assertEqual(cm["reddwarf_proxy_swift_auth_url"], config.get("snapshot", "swift_auth_url"))
            self.assertEqual("{0}:{1}".format(credential['tenant_id'], credential['user_name']), config.get("snapshot", "swift_auth_user"))
            self.assertEqual(credential["password"], config.get("snapshot", "swift_auth_key"))
            os.remove(file_name)
        except:
            self.assertTrue(False)