import json
import unittest

import mox
import pika

from smart_agent import SmartAgent
from smartagent_messaging import MessagingService

class SmartAgentUnitTest(unittest.TestCase):  
    def setUp (self):
        self.mox = mox.Mox()
        self.mock_msg_service = self.mox.CreateMock(MessagingService)
        self.agent = SmartAgent(self.mock_msg_service)
        
#    def test_start_connection(self):
#        self.mox.StubOutWithMock(self.real_agent, "connection")
#        self.mox.StubOutWithMock(self.real_agent, "channel")
#        self.mox.StubOutWithMock(self.real_agent, "exchange")
#        self.mox.StubOutWithMock(self.real_agent, "result")
#        self.mox.StubOutWithMock(self.real_agent, "queue_name")
#        self.mox.StubOutWithMock(self.real_agent, "queue_bind")
#        self.mox.ReplayAll()
#        self.real_agent.start_connection()
#        self.mox.UnsetStubs()
#        self.mox.VerifyAll()
     
#    def test_start_consuming(self):
#        self.mock_agent.start_consuming()
#        self.mox.ReplayAll()
#        self.mock_agent.start_consuming()
#        self.mox.VerifyAll()
        
#    def test_send_response(self):
#        self.mock_agent.send_response(message='message', props='properties', 
#                                      response_id='response_id')
#        self.mox.ReplayAll()
#        self.mock_agent.send_response(message='message', props='properties', 
#                                      response_id='response_id')
#        self.mox.VerifyAll()   
        
#    def test_end_response(self):
#        self.mock_agent.end_response(props='properties', response_id='response_id')
#        self.mox.ReplayAll()
#        self.mock_agent.end_response(props='properties', response_id='response_id')
#        self.mox.VerifyAll()
        
#    def test_malformed_JSON(self):
#        # Test to see if malformed JSON is properly handled.   
#        message = r'''} I'm malformed {'''
#        self.mock_agent.process_message(channel='channel', method='method',
#            props='properties', body=message) #AndReturn...what?
#        self.mox.ReplayAll()
#        result = self.mock_agent.process_message(channel='channel', 
#            method='method', props='properties', body=message)
#        self.assertEqual(result, "KeyError")
#        self.mox.VerifyAll()
        
#    def test_JSON(self):
#        message = r'''{"method": "test"}'''
#        pass
