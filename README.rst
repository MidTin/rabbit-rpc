==========
Rabbit RPC 
==========

简述
----

这是对 RabbitMQ 的 Pika_ 库进行封装的，一套简易 RPC 客户端/服务端库。


安装说明
--------

::

    pip install rabbit-rpc
    


使用事例
--------

服务端
~~~~~~

::

    # project/consumers.py

    from rabbit_rpc.consumer import consumer

    @consumer(name='add')
    def add(a, b):
        return a + b


    # project shell
    rabbit_rpc worker --amqp 'amqp://guest:guest@localhost:5672/'


    # with django

    rabbit_rpc worker --amqp 'amqp://guest:guest@localhost:5672/' --django
    


客户端
~~~~~~

::
    
    from rabbit_rpc.client import RPCClient

    client = RPCClient(amqp_url='amqp://guest:guest@localhost:5672/')
    ret = client.call_add(1, 1, timeout=1)

    # or ignore result
    client.call_add(1, 1, ignore_result=True)

    # specify routing_key
    client.call_add(1, 1, routing_key='default')


.. _Pika: https://github.com/pika/pika
