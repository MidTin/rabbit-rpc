# -*- coding: utf-8 -*-
import logging
import json
import time
import uuid

import pika

from .exceptions import (ERROR_FLAG, HAS_ERROR, NO_ERROR, RemoteFunctionError,
                         RemoteCallTimeout)

logger = logging.getLogger(__name__)


class RPCClient(object):

    def __init__(self, amqp_url=None, conn_parameters=None, exchange='default'):
        assert any((amqp_url, conn_parameters)), 'must be provide amqp_url or conn_parameters'

        self._results = {}
        self._exchange = exchange
        self.url = amqp_url

        if conn_parameters:
            self.conn_parameters = conn_parameters
        else:
            self.conn_parameters = pika.URLParameters(self.url)

        self.connect()

    def connect(self):
        self.connection = pika.BlockingConnection(self.conn_parameters)
        self.channel = self.connection.channel()

    def setup_callback_queue(self):
        if not hasattr(self, 'callback_queue'):
            ret = self.channel.queue_declare(exclusive=True, auto_delete=True)
            self.callback_queue = ret.method.queue
            self.channel.queue_bind(self.callback_queue, self._exchange)
            self.channel.basic_consume(
                self.on_response, queue=self.callback_queue)

    def on_response(self, channel, basic_deliver, props, body):
        ret = json.loads(body)
        if props.headers.get(ERROR_FLAG, NO_ERROR) == HAS_ERROR:
            ret = RemoteFunctionError(ret)

        self._results[props.correlation_id] = ret

    def get_response(self, correlation_id, timeout=None):
        stoploop = time.time() + timeout if timeout is not None else 0
        while stoploop > time.time() or timeout is None:
            self.connection.process_data_events()
            if correlation_id in self._results:
                return self._results.pop(correlation_id)
            self.connection.sleep(0.1)

        raise RemoteCallTimeout()

    def publish_message(self, exchange, routing_key, body, headers=None):
        corr_id = str(uuid.uuid4())

        self.channel.basic_publish(
            exchange=exchange,
            routing_key=routing_key,
            properties=pika.BasicProperties(
                reply_to=self.callback_queue,
                headers=headers,
                correlation_id=corr_id,
            ),
            body=json.dumps(body))

        return corr_id

    def skip_response(self, correlation_id):
        self._results.pop(correlation_id, None)

    def call(self, consumer_name):

        def func(*args, **kwargs):
            """Call the remote function.

            :param bool ignore_result: Ignore the result return immediately.
            :param str exchange: The exchange name consists of a non-empty.
            :param str routing_key: The routing key to bind on.
            :param float timeout: if waiting the result over timeount seconds,
                                  RemoteCallTimeout will be raised .
            """
            ignore_result = kwargs.pop('ignore_result', False)
            exchange = kwargs.pop('exchange', self._exchange)
            routing_key = kwargs.pop('routing_key', self._exchange)
            timeout = kwargs.pop('timeout', None)

            if not ignore_result:
                self.setup_callback_queue()

            try:
                if timeout is not None:
                    timeout = float(timeout)
            except (ValueError, TypeError):
                raise ValueError("'timeout' is expected a float.")

            payload = {
                'args': args,
                'kwargs': kwargs,
            }

            corr_id = self.publish_message(
                exchange,
                routing_key,
                body=payload,
                headers={'consumer_name': consumer_name})

            logger.info('Sent remote call: %s', consumer_name)
            if not ignore_result:
                try:
                    ret = self.get_response(corr_id, timeout)
                except RemoteCallTimeout:
                    raise RemoteCallTimeout(
                        "Calling remote function '%s' timeout." % consumer_name)

                if isinstance(ret, RemoteFunctionError):
                    raise ret

                return ret

            self.skip_response(corr_id)

        func.__name__ = consumer_name
        return func

    def __getattribute__(self, key):
        if key.startswith('call_'):
            _, consumer_name = key.split('call_')
            return self.call(consumer_name)

        return super(RPCClient, self).__getattribute__(key)

    def __del__(self):
        self.connection.close()
