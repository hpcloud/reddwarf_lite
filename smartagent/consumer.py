#!/usr/bin/env python

import pika
import json
import utils

#host = '15.185.172.164'
host = '15.185.161.51'


""" declare connection to rabbitmq server """
connection = pika.BlockingConnection(pika.ConnectionParameters(host))

""" establish message channel """
channel = connection.channel()

print ' [*] Waiting for logs. To exit press CTRL+C'

""" the agent work starts here """
def callback(ch, method, properties, body):
    result = json.loads(body)
    print ' [*] %r' % result
    utils.exec_command(result['command'], result['isAdmin'], result['args'])


""" consume message from queue demo """
channel.basic_consume(callback,queue='demo',no_ack=True)

""" now consume """
channel.start_consuming()
