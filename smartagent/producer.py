#!/usr/bin/env python

import pika

#host = '15.185.172.164'
host = '15.185.161.51'
queue_name = 'demo'
rting_key = 'demo'

""" define the message to publish """
message1 = '''{"command": "password_reset", "isAdmin": "True",  "args": [1,2,3]}'''
message2 = '''{"command": "new_user", "isAdmin": "True",  "args": [1,2,4]}'''
message3 = '''{"command": "password_reset", "isAdmin": "False",  "args": [1,2,9]}'''

""" declare connection to rabbitmq server """
connection = pika.BlockingConnection(pika.ConnectionParameters(host))

""" establish message channel """
channel = connection.channel()

""" declare queue for publish """
channel.queue_declare(queue=queue_name)


""" now publish to the specified queue of default exchange """
channel.basic_publish(exchange='',
                      routing_key='demo',
                      body=message1)

print " [x] Sent %r" % (message1,)

channel.basic_publish(exchange='',
                      routing_key='demo',
                      body=message2)

print " [x] Sent %r" % (message2,)

channel.basic_publish(exchange='',
                      routing_key='demo',
                      body=message3)

print " [x] Sent %r" % (message3,)

connection.close()

