# -*- coding: utf-8 -*-
import logging

from .base import Connector
from .consumer import MessageDispatcher
from .queue import Queue

logger = logging.getLogger(__name__)


class RPCServer(Connector):

    def __init__(self, consumers, queue, *args, **kwargs):
        self._consumers = consumers
        self.default_queue = queue or self.DEFUALT_QUEUE

        super(RPCServer, self).__init__(*args, **kwargs)

    def on_exchange_declareok(self, unused_frame, userdata):
        self.setup_queues()

    def _setup_queue(self, queue_name):
        dispatcher = MessageDispatcher(self._channel, self._exchange)
        queue = Queue(queue_name, dispatcher)
        self._queues[queue_name] = queue
        return queue

    def setup_default_queue(self):
        return self._setup_queue(self.default_queue)

    def setup_queues(self):
        """Setup the queue on RabbitMQ by invoking the Queue.Declare RPC
        command.

        :param str|unicode queue_name: The name of the queue to declare.
        """
        default_queue = self.setup_default_queue()

        for c in self._consumers:

            if c.queue is None:
                queue = default_queue
            else:
                try:
                    queue = self._queues[c.queue]
                    if queue.exclusive or c.exclusive:
                        raise ValueError(
                            'Consumer %s is set exclusive with queue %s, but there '
                            'are other consumers already exist.' % (c.name,
                                                                    queue.name))

                except KeyError:
                    queue = self._setup_queue(c.queue)

            queue.add_consumer(c)

        # setup the queue on RabbitMQ
        for queue_name in self._queues.keys():
            self._channel.queue_declare(queue=queue_name, durable=True)
            self._channel.queue_bind(queue_name, exchange=self._exchange)

        self.start_consuming()

    def start_consuming(self):
        self._channel.add_on_cancel_callback(self.on_consumer_cancelled)

        for queue in self._queues.values():
            consumer_tag = self._channel.basic_consume(
                queue.name, queue.dispatcher)
            queue.dispatcher.consumer_tag = consumer_tag

        logger.info(self._queues)
        logger.info('Start consuming..')

    def on_consumer_cancelled(self, method_frame):
        """Invoked by pika when RabbitMQ sends a Basic.Cancel for a consumer
        receiving messages.

        :param pika.frame.Method method_frame: The Basic.Cancel frame

        """
        logger.info('Consumer was cancelled remotely, shutting down: %r',
                    method_frame)
        self.close_channel()
