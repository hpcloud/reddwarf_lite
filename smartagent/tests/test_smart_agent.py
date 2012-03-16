import json
import os
import sys
import unittest

import mox

cwd = os.getcwd()
os.chdir("..")
sys.path.append(os.getcwd())
from smartagent import SmartAgent
from smartagent_messaging import MessagingService
from check_mysql_status import MySqlChecker
from command_handler import MysqlCommandHandler
os.chdir(cwd)


class SmartAgentUnitTest(unittest.TestCase):

    def setUp (self):
        self.mox = mox.Mox()
        self.mock_msg_service = self.mox.CreateMock(MessagingService)
        self.agent = SmartAgent(self.mock_msg_service)

    def test_unsupported_method(self):
        """Test to see that a message with an unsupported method generates
           the correct response."""

        message = r'''{"method": "unsupported"}'''
        result = self.agent.process_message(msg=json.loads(message))
        self.mox.ReplayAll()

        self.assertEqual(result, {'failure': 'unsupported_method', 'result': None})
        self.mox.VerifyAll()

    def test_missing_method(self):
        """Test to see that a missing method key generates an error."""

        message = r'''{"not_method": "test"}'''
        result = self.agent.process_message(msg=json.loads(message))
        self.mox.ReplayAll()

        self.assertEqual(result, {'failure': 'missing_method', 'result': None})
        self.mox.VerifyAll()

    def test_check_mysql_status_running(self):
        """Test to see that the correct response is returned when a MySQL
           server is running."""

        self.agent.checker = self.mox.CreateMock(MySqlChecker)
        self.mox.StubOutWithMock(self.agent.checker, "check_if_running")
        self.agent.checker.check_if_running(number_of_checks=5,
                                            sleep_time_seconds=3).AndReturn(True)
        self.mox.ReplayAll()

        result = self.agent.check_status()
        self.assertEqual(result, 1)
        self.mox.VerifyAll()

    def test_check_mysql_status_not_running(self):
        """Test to see that the correct response is returned when a MySQL
           server is not running."""

        self.agent.checker = self.mox.CreateMock(MySqlChecker)
        self.mox.StubOutWithMock(self.agent.checker, "check_if_running")
        self.agent.checker.check_if_running(number_of_checks=5,
                                            sleep_time_seconds=3).AndReturn(False)
        self.mox.ReplayAll()

        result = self.agent.check_status()
        self.assertEqual(result, 0)
        self.mox.VerifyAll()

    def test_create_database(self):
        """Test to see that the correct response is returned from a create
           database operation."""

        msg = json.loads(r"""{"args": {"database": "test"}}""")
        self.agent.handler = self.mox.CreateMock(MysqlCommandHandler)
        self.mox.StubOutWithMock(self.agent.handler, "create_database")
        self.agent.handler.create_database(msg['args']['database']).AndReturn("SUCCESS")
        self.mox.ReplayAll()

        result = self.agent.create_database(msg)
        self.assertEqual(result, "SUCCESS")
        self.mox.VerifyAll()



    def tearDown(self):
        self.mox.UnsetStubs()


if __name__ == '__main__':
    unittest.main()
