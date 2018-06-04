# -*- coding: utf-8 -*-
import logging
import json
from threading import Thread
import time
import uuid

import pika

from .base import Connector
from .exceptions import (ERROR_FLAG, HAS_ERROR, NO_ERROR, RemoteFunctionError,
                         RemoteCallTimeout)

logger = logging.getLogger(__name__)


class RPCClient(Connector):

    def __init__(self, *args, **kwargs):
        super(RPCClient, self).__init__(*args, **kwargs)

        self.callback_queue = None
        self._results = {}

        self._loop_thread = Thread(target=self.run)
        self._loop_thread.daemon = True
        self._loop_thread.start()

        self.ready = False

        self.wait_for_ready()

    def wait_for_ready(self):
        while not self.ready:
            time.sleep(0.1)
            continue

        logger.info('RPCClient is ready...')

    def set_ready(self):
        self.ready = True

    def on_exchange_declareok(self, unused_frame):
        self.callback_queue = str(uuid.uuid4())
        self.setup_queue(self.callback_queue, exclusive=True)
        self._channel.basic_consume(
            self.on_response, no_ack=True, queue=self.callback_queue)

        self.set_ready()

    def setup_queue(self,
                    queue_name,
                    callback=None,
                    exchange=None,
                    durable=False,
                    exclusive=False,
                    auto_delete=False):

        if exchange is None:
            exchange = self._exchange

        self._channel.queue_declare(
            None, queue_name, durable=durable, exclusive=exclusive,
            auto_delete=auto_delete)
        self._channel.queue_bind(callback, queue_name, exchange)

    def on_response(self, channel, basic_deliver, props, body):
        ret = json.loads(body)
        if props.headers.get(ERROR_FLAG, NO_ERROR) == HAS_ERROR:
            ret = RemoteFunctionError(ret)

        self._results[props.correlation_id] = ret

    def publish_message(self, exchange, routing_key, body, headers=None):
        corr_id = str(uuid.uuid4())

        self._channel.basic_publish(
            exchange=exchange,
            routing_key=routing_key,
            properties=pika.BasicProperties(
                reply_to=self.callback_queue,
                headers=headers,
                correlation_id=corr_id,
            ),
            body=json.dumps(body))

        return corr_id

    def get_response(self, correlation_id, timeout=None):
        stoploop = time.time() + timeout if timeout is not None else 0

        while stoploop > time.time() or timeout is None:
            if correlation_id in self._results:
                time.sleep(0.05)
                return self._results.pop(correlation_id)

        raise RemoteCallTimeout()

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
            routing_key = kwargs.pop('routing_key', self.DEFUALT_QUEUE)
            timeout = kwargs.pop('timeout', None)

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
