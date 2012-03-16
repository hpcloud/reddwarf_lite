# Copyright 2012 HP Software, LLC
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
import paths
from singleton import Singleton
import os
import pika
import json
import logging

__author__ = 'dragosmanolescu'
__email__ = 'dragosm@hp.com'
__python_version__ = '2.7.2'

LOG = logging.getLogger(paths.smartagent_name)

@Singleton
class MessagingService():
    def __init__(self,
                 callback=None,
                 host_address='15.185.163.167',  #TODO: remove hardcoded IP
                 exchange_name='nova'):  #TODO: remove hardcoded uid
        self.callback = callback
        self.mq_host = host_address
        self.exchange_name = exchange_name

        # Dynamically set routing key using the instance hostname.
        self.routing_key = os.uname()[1]

        # Set MQ server values.
        self.connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=self.mq_host))
        self.channel = self.connection.channel()
        self.exchange = self.channel.exchange_declare(
            exchange=self.exchange_name,
            type='topic')
        self.result = self.channel.queue_declare(exclusive=True)
        self.queue_name = self.result.method.queue
        self.queue_bind = self.channel.queue_bind(
            exchange=self.exchange_name,
            queue=self.queue_name,
            routing_key=self.routing_key)

    def start_consuming(self):
        """Sets the properties for message consumption and then establishes
           a connection with the MQ server.

           Arguments:   self
           Return type: void"""
        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(self.on_request, queue=self.queue_name)

        # Consumer loop to read incoming messages.
        LOG.debug("Awaiting requests from RedDwarf API server>")
        reader = self.channel
        reader.start_consuming()

    def on_request(self, channel, method, props, body):
        """ Callback for MQ message consumer.  Called whenever a message is
            consumed.

            Arguments:   self
                         channel -- The connection object for the MQ server
                         method  -- Delivery properties for the channel object
                         props   -- Properties for the connection object
                         body    -- String containing the actual message
            Return type: None"""

        LOG.debug("Received %s",body)
        # Make sure that we properly handle malformed JSON strings.
        try:
            msg = json.loads(body)
        except ValueError:
            channel.basic_ack(delivery_tag=method.delivery_tag)
            LOG.error("ValueError exception - improperly formatted JSON: %s",
                body)
        else:
            channel.basic_ack(delivery_tag=method.delivery_tag)
            if self.callback is not None:
                response = self.callback(msg)
            else:
                response = {'result' : None, 'failure' : None}

            # If the '_msg_id' key is present, we need a response to the
            # rpc.call.
            if '_msg_id' in msg:
                LOG.debug("Responding to rpc.call: %s", response)

                # The '_msg_id' key is used to identify the MQ channel for
                # responding (enables mapping to exchange & routing keys).
                response_id = msg['_msg_id']
                self.send_response(response, props, response_id)
                self.end_response(props, response_id)

    def send_response(self, message, props, response_id):
        """Sends response back to the exclusive direct exchange for rpc.call -
           the message should be a dictionary.

           Arguments:   self
                        message -- Dictionary containing the response to API
                                   server
                        props   -- Properties for the connection object
                        response_id -- String containing the exchange to use
                                       for the response
           Return type: None"""

        self.channel.basic_publish(
            exchange=response_id,
            routing_key=response_id,
            properties=pika.BasicProperties(correlation_id=props.correlation_id),
            body=str(message))

    def end_response(self, props, response_id):
        """Send end response signal back when there are no more responses to
           send so the rpc.call client on API Server can disconnect the channel
           (required by the RedDwarf RPC protocol).

           Arguments:   self
                        props   -- Properties for the connection object
                        response_id -- String containing the exchange to use
                                       for the response
           Return type: None"""

        # The end response signal is defined by the RPC protocol.
        end_message = {'result': None, 'failure': None}
        self.send_response(end_message, props, response_id)

    def phone_home(self, message, exchange='phonehome'):
        """Sends phone home message to the direct exchange -
           the message should be a dictionary.

           Arguments:   self
                        message -- Dictionary containing the phone home message
                        exchange -- String containing the name of the phone home exchange
           Return type: None"""
        self.channel.basic_publish(exchange=exchange,
            routing_key=exchange,
            body=str(message))
