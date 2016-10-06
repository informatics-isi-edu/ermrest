#!/usr/bin/python

import json
import pika
import datetime
import pytz

polling_seconds = 300.0
coalesce_seconds = 1

notice_exchange = 'ermrest_changes'

connection = pika.BlockingConnection(
    pika.ConnectionParameters(
        host='localhost'
    )
)

print 'Connected.'

notice_channel = connection.channel()
notice_channel.exchange_declare(exchange=notice_exchange, type='fanout')
notice_queue_name = notice_channel.queue_declare(exclusive=True).method.queue
notice_channel.queue_bind(exchange=notice_exchange, queue=notice_queue_name)

print 'Channels opened.'

### Generic ERMrest+AMQP event-loop...
try:
    polling_gen = notice_channel.consume(notice_queue_name, exclusive=True, inactivity_timeout=polling_seconds)
    coalesce_gen = notice_channel.consume(notice_queue_name, exclusive=True, inactivity_timeout=coalesce_seconds)

    # follow channel with polling_seconds periodic wakeup even when idle
    for result in polling_gen:
        print 'Woke up on %s.' % ('notification' if result else 'timeout')
        # ... and delay for up to coalesce_seconds to combine multiple notices into one wakeup
        while coalesce_gen.next() is not None:
            print 'Coalesced message.'

finally:
    notice_channel.cancel()

connection.close()
